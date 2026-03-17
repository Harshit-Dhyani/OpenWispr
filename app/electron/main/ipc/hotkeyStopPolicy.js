/**
 * Hotkey stop policy for floating window result visibility
 * Determines whether to keep the floating transcription result visible after
 * recording stops based on user action and settings. Exports: shouldKeepFloatingResultVisible
 * @module hotkeyStopPolicy
 */
function shouldKeepFloatingResultVisible({
  showFloatingWindow,
  pendingAction,
  keepResultVisible = false,
}) {
  return Boolean(showFloatingWindow) && pendingAction !== "cancel" && keepResultVisible === true;
}

module.exports = {
  shouldKeepFloatingResultVisible,
};
