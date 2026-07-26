/**
 * Utility to parse UTC date strings from backend and convert them accurately
 * into the viewing user's local region & timezone.
 */
export function formatToUserLocalTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";

  let normalizedStr = dateStr;
  if (typeof dateStr === "string") {
    // Convert "YYYY-MM-DD HH:MM:SS" to ISO format "YYYY-MM-DDTHH:MM:SS"
    normalizedStr = dateStr.replace(" ", "T");

    // Suffix "Z" if no timezone designation is present so JS knows it is UTC
    if (!normalizedStr.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(normalizedStr)) {
      normalizedStr += "Z";
    }
  }

  const dateObj = new Date(normalizedStr);
  if (isNaN(dateObj.getTime())) return String(dateStr);

  // Uses browser's native locale and local timezone automatically
  return dateObj.toLocaleString(undefined, {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}
