/**
 * Hold mode hotkey handling for recording control
 * Parses accelerator strings, normalizes modifiers across platforms, manages
 * iohook key listeners for hold-to-record functionality. Exports: parseHoldAccelerator,
 * createHoldModeController
 * @module holdModeHotkeys
 */
function normalizeModifierToken(token, platform) {
  const normalized = String(token || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === "commandorcontrol" || normalized === "cmdorctrl") {
    return platform === "darwin" ? "meta" : "ctrl";
  }
  if (normalized === "command" || normalized === "cmd" || normalized === "super" || normalized === "meta") {
    return "meta";
  }
  if (normalized === "control" || normalized === "ctrl") {
    return "ctrl";
  }
  if (normalized === "alt" || normalized === "option") {
    return "alt";
  }
  if (normalized === "shift") {
    return "shift";
  }
  return null;
}

function normalizeMainKeyToken(token) {
  const normalized = String(token || "").trim();
  if (!normalized) {
    return null;
  }
  const upper = normalized.toUpperCase();
  if (/^[A-Z0-9]$/.test(upper)) {
    return upper;
  }
  if (/^F([1-9]|1[0-2])$/.test(upper)) {
    return upper;
  }
  if (upper === "SPACE") {
    return "SPACE";
  }
  if (upper === "ENTER" || upper === "RETURN") {
    return "ENTER";
  }
  if (upper === "TAB") {
    return "TAB";
  }
  if (upper === "ESC" || upper === "ESCAPE") {
    return "ESCAPE";
  }
  return null;
}

function parseHoldAccelerator(accelerator, platform = process.platform) {
  if (!accelerator || typeof accelerator !== "string") {
    return null;
  }

  const tokens = accelerator
    .split("+")
    .map((part) => part.trim())
    .filter(Boolean);

  if (!tokens.length) {
    return null;
  }

  const modifiers = {
    ctrl: false,
    alt: false,
    shift: false,
    meta: false,
  };
  let key = null;

  for (const token of tokens) {
    const modifier = normalizeModifierToken(token, platform);
    if (modifier) {
      modifiers[modifier] = true;
      continue;
    }

    if (key) {
      return null;
    }
    key = normalizeMainKeyToken(token);
  }

  if (!key) {
    return null;
  }

  return { accelerator, modifiers, key };
}

function normalizeEventKey(event) {
  if (!event || typeof event !== "object") {
    return null;
  }

  const rawcode = Number(event.rawcode);
  if (Number.isInteger(rawcode)) {
    if (rawcode >= 65 && rawcode <= 90) {
      return String.fromCharCode(rawcode);
    }
    if (rawcode >= 48 && rawcode <= 57) {
      return String.fromCharCode(rawcode);
    }
    if (rawcode >= 112 && rawcode <= 123) {
      return `F${rawcode - 111}`;
    }
    if (rawcode === 32) {
      return "SPACE";
    }
    if (rawcode === 13) {
      return "ENTER";
    }
    if (rawcode === 9) {
      return "TAB";
    }
    if (rawcode === 27) {
      return "ESCAPE";
    }
  }

  const keychar = event.keychar;
  if (typeof keychar === "string" && keychar.trim()) {
    return keychar.trim().toUpperCase();
  }
  if (Number.isInteger(keychar) && keychar > 0 && keychar < 128) {
    return String.fromCharCode(keychar).toUpperCase();
  }

  return null;
}

function modifiersMatch(definition, event) {
  const expected = definition.modifiers;
  return (
    Boolean(event.ctrlKey) === expected.ctrl &&
    Boolean(event.altKey) === expected.alt &&
    Boolean(event.shiftKey) === expected.shift &&
    Boolean(event.metaKey) === expected.meta
  );
}

function eventMatchesAccelerator(definition, event) {
  return modifiersMatch(definition, event) && normalizeEventKey(event) === definition.key;
}

function shouldReleaseAccelerator(definition, event) {
  if (normalizeEventKey(event) === definition.key) {
    return true;
  }

  const expected = definition.modifiers;
  return (
    (expected.ctrl && !event.ctrlKey) ||
    (expected.alt && !event.altKey) ||
    (expected.shift && !event.shiftKey) ||
    (expected.meta && !event.metaKey)
  );
}

function addListener(hook, eventName, handler) {
  if (typeof hook.on === "function") {
    hook.on(eventName, handler);
    return;
  }
  throw new Error("iohook does not expose an on() listener API");
}

function removeListener(hook, eventName, handler) {
  if (typeof hook.off === "function") {
    hook.off(eventName, handler);
    return;
  }
  if (typeof hook.removeListener === "function") {
    hook.removeListener(eventName, handler);
  }
}

function createHoldModeController({
  platform = process.platform,
  loadHook = () => require("iohook"),
  onPress = async () => {},
  onRelease = async () => {},
  logger = console,
} = {}) {
  let hook = null;
  let started = false;
  let bindings = [];
  let keydownHandler = null;
  let keyupHandler = null;

  function clear() {
    if (hook && keydownHandler) {
      removeListener(hook, "keydown", keydownHandler);
    }
    if (hook && keyupHandler) {
      removeListener(hook, "keyup", keyupHandler);
    }
    if (hook && started && typeof hook.stop === "function") {
      try {
        hook.stop();
      } catch (error) {
        logger.warn?.("[main] Failed to stop hold-mode hook:", error.message);
      }
    }
    bindings = [];
    keydownHandler = null;
    keyupHandler = null;
    started = false;
    hook = null;
  }

  function isSupported() {
    try {
      loadHook();
      return true;
    } catch {
      return false;
    }
  }

  function configure(nextBindings) {
    clear();

    const parsedBindings = (nextBindings || [])
      .map((binding) => {
        const definition = parseHoldAccelerator(binding.accelerator, platform);
        if (!definition) {
          return null;
        }
        return {
          ...binding,
          definition,
          active: false,
        };
      })
      .filter(Boolean);

    if (!parsedBindings.length) {
      return { success: true, enabled: false };
    }

    try {
      hook = loadHook();
    } catch (error) {
      return {
        success: false,
        error: "Hold mode requires the optional iohook dependency to be installed.",
      };
    }

    bindings = parsedBindings;
    keydownHandler = (event) => {
      for (const binding of bindings) {
        if (binding.active || !eventMatchesAccelerator(binding.definition, event)) {
          continue;
        }
        binding.active = true;
        void onPress(binding.source);
      }
    };
    keyupHandler = (event) => {
      for (const binding of bindings) {
        if (!binding.active || !shouldReleaseAccelerator(binding.definition, event)) {
          continue;
        }
        binding.active = false;
        void onRelease(binding.source);
      }
    };

    addListener(hook, "keydown", keydownHandler);
    addListener(hook, "keyup", keyupHandler);
    if (typeof hook.start === "function") {
      hook.start();
      started = true;
    }

    return {
      success: true,
      enabled: true,
      bindings: parsedBindings.map((binding) => binding.accelerator),
    };
  }

  return {
    configure,
    clear,
    isSupported,
  };
}

module.exports = {
  parseHoldAccelerator,
  normalizeEventKey,
  eventMatchesAccelerator,
  shouldReleaseAccelerator,
  createHoldModeController,
};
