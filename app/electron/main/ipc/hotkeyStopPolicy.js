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
