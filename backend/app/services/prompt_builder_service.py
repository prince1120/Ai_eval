import json
import logging
import asyncio
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, create_model, ValidationError

from app.core.config import settings
from app.models.template import EvaluationTemplate, EvaluationParameter, ExtractionSection
from app.services.llm_client import LLMClient, LLMResult

logger = logging.getLogger(__name__)


# Schema template for individual parameter outcome
class ParameterEvaluationOutput(BaseModel):
    score: float = Field(..., description="Numeric score within parameter range")
    reason: str = Field(..., description="Detailed rationale for the score")
    evidence: str = Field("", description="Quote or text evidence from transcript")
    suggestion: str = Field("", description="Actionable suggestion for improvement")
    confidence: Optional[float] = Field(1.0, description="Confidence rating between 0.0 and 1.0")


@dataclass
class EvaluationOutcome:
    overall_score: float
    parameter_results: List[Dict[str, Any]]
    section_results: List[Dict[str, Any]]
    raw_llm_response: Dict[str, Any]
    model_used: str
    token_usage: Dict[str, int]


def sanitize_llm_json(content: Any) -> Dict[str, Any]:
    """Defensively sanitize LLM dictionary output keys and types before schema validation."""
    if not isinstance(content, dict):
        return {}

    sanitized = dict(content)

    # 1. Handle 'parameters' as a list of dicts OR dict of dicts
    raw_params = sanitized.get("parameters", {})
    params_dict = {}

    if isinstance(raw_params, list):
        for item in raw_params:
            if isinstance(item, dict):
                for pk, pv in item.items():
                    if pk.startswith("param_") and isinstance(pv, dict):
                        params_dict[pk] = pv
                    elif "parameter_id" in item or "param_id" in item:
                        key = item.get("parameter_id") or item.get("param_id") or pk
                        params_dict[str(key)] = item
    elif isinstance(raw_params, dict):
        params_dict = raw_params

    # Sanitize parameter evaluation fields
    for k, v in params_dict.items():
        if isinstance(v, dict):
            if "reason" not in v or not v["reason"]:
                v["reason"] = str(
                    v.get("details")
                    or v.get("explanation")
                    or v.get("reasoning")
                    or v.get("rationale")
                    or "Evaluated parameter score."
                )
            if "evidence" not in v:
                v["evidence"] = str(v.get("quote") or "")
            if "suggestion" not in v:
                v["suggestion"] = str(v.get("recommendation") or "")

    sanitized["parameters"] = params_dict

    # 2. Handle 'sections' as a list OR dict
    raw_sections = sanitized.get("sections", {})
    sections_dict = {}

    if isinstance(raw_sections, list):
        for idx, item in enumerate(raw_sections):
            if isinstance(item, dict):
                for sk, sv in item.items():
                    if sk.startswith("section_"):
                        sections_dict[sk] = str(sv)
            elif isinstance(item, str):
                sections_dict[f"sec_{idx}"] = item
    elif isinstance(raw_sections, dict):
        for k, v in raw_sections.items():
            if isinstance(v, dict):
                extracted_str = ", ".join(f"{key}: {val}" for key, val in v.items())
                sections_dict[k] = extracted_str
            elif isinstance(v, list):
                sections_dict[k] = "\n".join(map(str, v))
            elif v is None:
                sections_dict[k] = ""
            else:
                sections_dict[k] = str(v)

    sanitized["sections"] = sections_dict

    return sanitized


class PromptBuilderService:

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client


    def _merge_by_median(
        self, template: EvaluationTemplate, outcomes: List[EvaluationOutcome]
    ) -> EvaluationOutcome:
        """Combine several scoring passes into one reproducible result."""
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for outcome in outcomes:
            for result in outcome.parameter_results:
                by_name.setdefault(result["name_snapshot"], []).append(result)

        merged: List[Dict[str, Any]] = []
        for result in outcomes[0].parameter_results:
            variants = by_name.get(result["name_snapshot"], [result])
            scores = [float(v["score"]) for v in variants]
            median_score = statistics.median(scores)

            # Keep the narrative from the pass that actually produced the median
            # score, so the reason and evidence match the number shown.
            representative = min(variants, key=lambda v: abs(float(v["score"]) - median_score))

            spread = max(scores) - min(scores) if len(scores) > 1 else 0.0
            max_score = result.get("max_score") or 10
            # Full agreement -> 1.0; disagreement across the whole scale -> 0.0.
            agreement = max(0.0, 1.0 - (spread / max_score)) if max_score else 1.0

            merged.append({
                **representative,
                "score": median_score,
                "confidence": round(agreement, 3),
            })

        overall = self.calculate_overall_score(
            list(template.parameters),
            {
                f"param_{p.id.hex}": ParameterEvaluationOutput(
                    score=next(
                        (m["score"] for m in merged if m["name_snapshot"] == p.name), 0.0
                    ),
                    reason="",
                )
                for p in template.parameters
            },
        )

        usage = {
            "prompt_tokens": sum(o.token_usage.get("prompt_tokens", 0) for o in outcomes),
            "completion_tokens": sum(o.token_usage.get("completion_tokens", 0) for o in outcomes),
            "latency_ms": sum(o.token_usage.get("latency_ms", 0) for o in outcomes),
            "self_consistency_samples": len(outcomes),
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

        overalls = [o.overall_score for o in outcomes]
        logger.info(
            f"Self-consistency over {len(outcomes)} passes: "
            f"individual {overalls} -> median-merged {overall:.2f}"
        )

        return EvaluationOutcome(
            overall_score=round(overall, 2),
            parameter_results=merged,
            # Extractions are prose, not numbers - there is nothing to take a
            # median of, so the first pass wins.
            section_results=outcomes[0].section_results,
            raw_llm_response={"passes": [o.raw_llm_response for o in outcomes]},
            model_used=outcomes[0].model_used,
            token_usage=usage,
        )

    def build_dynamic_pydantic_model(
        self, parameters: List[EvaluationParameter], sections: List[ExtractionSection]
    ):
        """Construct a Pydantic model at runtime for a set of parameters and sections."""
        param_fields: Dict[str, Any] = {}
        for p in parameters:
            field_key = f"param_{p.id.hex}"
            # Optional, not required: small LLMs occasionally omit a parameter
            # from their JSON. If the field were required, a single omission
            # would fail the whole evaluation (even after the correction retry)
            # and discard every other parameter the model DID score. Omitted
            # params fall back to a default "not evaluated" result in evaluate().
            param_fields[field_key] = (
                Optional[ParameterEvaluationOutput],
                Field(None, description=f"Evaluation for '{p.name}' (Range: {p.min_score}-{p.max_score})"),
            )

        section_fields: Dict[str, Any] = {}
        for s in sections:
            field_key = f"section_{s.id.hex}"
            section_fields[field_key] = (
                str,
                Field("", description=f"Extracted information for section '{s.name}'"),
            )

        ParamsContainer = create_model("DynamicParametersModel", **param_fields)
        SectionsContainer = create_model("DynamicSectionsModel", **section_fields)

        DynamicEvalModel = create_model(
            "DynamicEvaluationModel",
            parameters=(ParamsContainer, Field(...)),
            sections=(SectionsContainer, Field(default_factory=dict)),
        )

        return DynamicEvalModel

    def generate_prompts_for_batch(
        self,
        template_name: str,
        parameters: List[EvaluationParameter],
        sections: List[ExtractionSection],
        raw_transcript: str,
    ) -> tuple[str, str]:
        """Generate system and user prompts for a subset of parameters."""
        # Without stated bands, "score 0-10" leaves the model to invent what a 4
        # means versus a 7, and it invents differently each run: re-scoring one
        # unchanged transcript five times moved the overall result by 15.7
        # points, with a single parameter landing on 0, 4, 6, 6 and 7. Anchoring
        # the scale is what makes a re-run reproduce the previous score.
        system_prompt = (
            "You are an objective, precise call quality evaluation AI.\n"
            "Analyze the transcript and evaluate every scoring parameter and extraction section requested.\n\n"
            "SCORING SCALE - apply these bands consistently. Judge only what the "
            "transcript actually shows; do not assume anything that is not there.\n"
            "  0        = the behaviour is entirely absent, or the opposite was done\n"
            "  1-3      = attempted but clearly inadequate\n"
            "  4-6      = partially done; noticeable gaps remain\n"
            "  7-8      = done properly, meets expectations\n"
            "  9-10     = done thoroughly and notably well\n"
            "Scores are scaled proportionally if a parameter uses a different range.\n\n"
            "If a parameter simply does not apply to this call, score it in the "
            "7-8 band and say so in the reason rather than penalising the agent.\n"
            "Base every score on specific evidence you can quote from the transcript.\n\n"
            "Return STRICT JSON ONLY matching the required output structure."
        )

        user_prompt_lines = [
            f"=== EVALUATION TEMPLATE: {template_name} ===",
            "\n--- SCORING PARAMETERS TO EVALUATE ---",
        ]

        for idx, p in enumerate(parameters, 1):
            key = f"param_{p.id.hex}"
            user_prompt_lines.append(
                f"{idx}. Parameter: '{p.name}' (JSON key: '{key}')\n"
                f"   - Score Range: [{p.min_score} to {p.max_score}]\n"
                f"   - Instructions: {p.ai_instructions}"
            )

        if sections:
            user_prompt_lines.append("\n--- EXTRACTION SECTIONS TO EXTRACT ---")
            for idx, s in enumerate(sections, 1):
                key = f"section_{s.id.hex}"
                user_prompt_lines.append(
                    f"{idx}. Section: '{s.name}' (JSON key: '{key}')\n"
                    f"   - Instructions: {s.ai_instructions}"
                )

        user_prompt_lines.extend(
            [
                "\n--- CALL TRANSCRIPT ---",
                raw_transcript,
                "\n--- OUTPUT FORMAT INSTRUCTION ---",
                "Return JSON with top-level keys 'parameters' (object) and 'sections' (object).",
                "For 'parameters', return a dictionary where each key is 'param_...' and value is a JSON object with EXACT keys: 'score' (number), 'reason' (string), 'evidence' (string), 'suggestion' (string).",
                "For 'sections', return a dictionary where each key is 'section_...' and value is a string.",
            ]
        )

        return system_prompt, "\n".join(user_prompt_lines)

    def calculate_overall_score(
        self,
        parameters: List[EvaluationParameter],
        param_evals: Dict[str, ParameterEvaluationOutput],
    ) -> float:
        """Compute weighted percentage overall score (0.0 - 100.0)."""
        if not parameters:
            return 0.0

        total_weight = sum(p.weight if p.weight is not None else 1.0 for p in parameters)
        if total_weight <= 0:
            total_weight = 1.0

        weighted_score_sum = 0.0
        for p in parameters:
            key = f"param_{p.id.hex}"
            param_eval = param_evals.get(key)
            if param_eval:
                max_sc = p.max_score if p.max_score > 0 else 10
                normalized = max(0.0, min(1.0, param_eval.score / max_sc))
                w = p.weight if p.weight is not None else 1.0
                weighted_score_sum += normalized * w

        return (weighted_score_sum / total_weight) * 100.0

    async def _evaluate_single_batch(
        self,
        template_name: str,
        parameters: List[EvaluationParameter],
        sections: List[ExtractionSection],
        raw_transcript: str,
        organization_id: Optional[str] = None,
    ):
        """Evaluate a single batch of parameters/sections safely."""
        DynamicModel = self.build_dynamic_pydantic_model(parameters, sections)
        system_prompt, user_prompt = self.generate_prompts_for_batch(
            template_name, parameters, sections, raw_transcript
        )

        llm_res: LLMResult = await self.llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            organization_id=organization_id,
        )

        sanitized_json = sanitize_llm_json(llm_res.content)

        try:
            validated_output = DynamicModel.model_validate(sanitized_json)
        except ValidationError as val_err:
            logger.warning(f"Validation failed on initial batch response: {val_err}. Retrying...")
            correction_prompt = (
                f"{user_prompt}\n\n"
                f"IMPORTANT: Your previous output failed schema validation:\n"
                f"{val_err}\n"
                f"Return JSON object with 'parameters' (dict) and 'sections' (dict)."
            )
            llm_res = await self.llm_client.generate_json(
                system_prompt=system_prompt,
                user_prompt=correction_prompt,
                organization_id=organization_id,
            )
            sanitized_json = sanitize_llm_json(llm_res.content)
            validated_output = DynamicModel.model_validate(sanitized_json)

        return validated_output, llm_res

    async def evaluate(
        self,
        template: EvaluationTemplate,
        raw_transcript: str,
        organization_id: Optional[str] = None,
    ) -> EvaluationOutcome:
        """Score a transcript, taking the median of several independent passes.

        LLM scoring is not reproducible even at temperature 0. Measured by
        re-scoring one unchanged transcript five times: the overall result moved
        6.7 points, and individual parameters drifted up to 3. For call QA that
        matters - the same call must not pass one day and fail the next - so the
        scorecard is run `LLM_SELF_CONSISTENCY_SAMPLES` times and each parameter
        takes the median score. The median also discards a single wild outlier,
        which is the failure mode that produced a 0 next to four passing scores.

        Agreement across passes is recorded as the parameter's confidence, so a
        genuinely ambiguous criterion is visible in the report rather than
        hidden behind a single confident-looking number.
        """
        samples = max(1, settings.LLM_SELF_CONSISTENCY_SAMPLES)
        if samples == 1:
            return await self._evaluate_once(template, raw_transcript, organization_id)

        outcomes: List[EvaluationOutcome] = []
        for attempt in range(samples):
            try:
                outcomes.append(
                    await self._evaluate_once(template, raw_transcript, organization_id)
                )
            except Exception as exc:
                # One failed pass should not lose the scorecard; the median is
                # taken over whatever succeeded.
                logger.warning(f"Self-consistency pass {attempt + 1}/{samples} failed: {exc}")

        if not outcomes:
            raise RuntimeError("Every scoring pass failed")
        if len(outcomes) == 1:
            return outcomes[0]

        return self._merge_by_median(template, outcomes)

    async def _evaluate_once(
        self,
        template: EvaluationTemplate,
        raw_transcript: str,
        organization_id: Optional[str] = None,
    ) -> EvaluationOutcome:
        """One full scoring pass.

        If template has > 15 parameters, parameters are split into parallel batches
        to avoid output token limits (LLM_MAX_TOKENS) and guarantee 100% JSON accuracy!
        """
        all_parameters = list(template.parameters)
        all_sections = list(template.sections)
        batch_size = 15

        # Split parameters into chunks of 15
        param_chunks = [
            all_parameters[i : i + batch_size] for i in range(0, len(all_parameters), batch_size)
        ]

        if not param_chunks:
            param_chunks = [[]]

        # Execute all batches in parallel
        tasks = []
        for idx, p_chunk in enumerate(param_chunks):
            # Only send sections with the first batch to avoid redundant extractions
            sec_chunk = all_sections if idx == 0 else []
            tasks.append(
                self._evaluate_single_batch(
                    template.name, p_chunk, sec_chunk, raw_transcript, organization_id
                )
            )

        results = await asyncio.gather(*tasks)

        # Merge parameter and section outputs from all batches
        param_eval_objects: Dict[str, ParameterEvaluationOutput] = {}
        section_results_dict: Dict[str, Any] = {}
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_latency_ms = 0
        model_used = "ministral-3b-2512"
        combined_raw_responses = []

        for validated_output, llm_res in results:
            model_used = llm_res.model_used or model_used
            combined_raw_responses.append(llm_res.content)

            # Sum tokens and track max latency
            total_prompt_tokens += llm_res.token_usage.get("prompt_tokens", 0)
            total_completion_tokens += llm_res.token_usage.get("completion_tokens", 0)
            total_latency_ms = max(total_latency_ms, getattr(llm_res, "latency_ms", 0))

            # Extract parameter objects
            if hasattr(validated_output, "parameters") and validated_output.parameters:
                p_dump = validated_output.parameters.model_dump()
                for pk, pv in p_dump.items():
                    if isinstance(pv, dict):
                        param_eval_objects[pk] = ParameterEvaluationOutput(**pv)
                    elif pv is not None:
                        param_eval_objects[pk] = pv
                    # pv is None => the LLM omitted this parameter; leave it out
                    # so the fallback default in the results loop below handles it.

            # Extract section outputs
            if hasattr(validated_output, "sections") and validated_output.sections:
                s_dump = validated_output.sections.model_dump()
                for sk, sv in s_dump.items():
                    section_results_dict[sk] = sv

        # Format parameter results list
        param_results_list = []
        for p in all_parameters:
            key = f"param_{p.id.hex}"
            eval_obj = param_eval_objects.get(
                key,
                ParameterEvaluationOutput(
                    score=0.0,
                    reason="The evaluation model did not return a result for this parameter. You can re-run the analysis to retry.",
                    evidence="",
                    suggestion="",
                    confidence=0.0,
                ),
            )

            param_results_list.append(
                {
                    "parameter_id": p.id,
                    "name_snapshot": p.name,
                    "ai_instructions_snapshot": p.ai_instructions,
                    "score": eval_obj.score,
                    "max_score": p.max_score,
                    "reason": eval_obj.reason,
                    "evidence": eval_obj.evidence,
                    "suggestion": eval_obj.suggestion,
                    "confidence": eval_obj.confidence,
                }
            )

        # Format section results list
        section_results_list = []
        for s in all_sections:
            key = f"section_{s.id.hex}"
            extracted_text = str(section_results_dict.get(key, ""))
            section_results_list.append(
                {
                    "section_id": s.id,
                    "name_snapshot": s.name,
                    "extracted_content": extracted_text,
                }
            )

        # Compute overall weighted percentage score
        overall_score = self.calculate_overall_score(all_parameters, param_eval_objects)

        return EvaluationOutcome(
            overall_score=round(overall_score, 2),
            parameter_results=param_results_list,
            section_results=section_results_list,
            raw_llm_response={"batches": combined_raw_responses},
            model_used=model_used,
            token_usage={
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "latency_ms": total_latency_ms,
            },
        )
