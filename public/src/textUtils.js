/**
 * Small text helpers shared by the app and the checkpoint engine.
 */

/** Lower-case, strip punctuation, collapse whitespace. */
export const normalize = (value) =>
  String(value ?? '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}']/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();

/** Split on whitespace, matching how checkpoint word indices are counted. */
export const getWords = (value) =>
  String(value ?? '').trim().split(/\s+/).filter(Boolean);
