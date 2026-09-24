// Fills form fields on the current page from the saved profile.
//
// This function is injected into the page with chrome.scripting.executeScript,
// so it must be self-contained: it can't use anything defined outside it.
// It only fills in fields. It never clicks buttons or submits forms, and it
// skips passwords, card numbers and other sensitive fields.
function fillPage(profile, overwrite) {
  // Checked in order, and the first match wins. Put more specific rules
  // before general ones (for example "email" before "address").
  const RULES = [
    { key: "email", autocomplete: ["email"], pattern: /e-?mail/ },
    { key: "phone", autocomplete: ["tel", "tel-national"], pattern: /phone|mobile|\btel\b|cell/ },
    { key: "firstName", autocomplete: ["given-name"], pattern: /first.?name|given.?name|fname|\bfirst\b/ },
    { key: "lastName", autocomplete: ["family-name"], pattern: /last.?name|surname|family.?name|lname|\blast\b/ },
    { key: "linkedin", autocomplete: [], pattern: /linked.?in/ },
    { key: "school", autocomplete: [], pattern: /school|university|college|institution/ },
    { key: "fullName", autocomplete: ["name"], pattern: /full.?name|your.?name|\bname\b/, exclude: /user|company|business|org|middle|nick/ },
    { key: "street", autocomplete: ["street-address", "address-line1"], pattern: /street|address|addr/, exclude: /line.?2|apt|suite|unit/ },
    { key: "city", autocomplete: ["address-level2"], pattern: /city|town/ },
    { key: "state", autocomplete: ["address-level1"], pattern: /\bstate\b|province|region/ },
    { key: "zip", autocomplete: ["postal-code"], pattern: /zip|postal|post.?code/ },
    { key: "country", autocomplete: ["country", "country-name"], pattern: /country/ },
    { key: "major", autocomplete: [], pattern: /major|field.?of.?study|discipline|degree/ },
    { key: "gradYear", autocomplete: [], pattern: /grad(uation)?.?(year|date)|class.?of|expected.?grad/ },
    { key: "website", autocomplete: ["url"], pattern: /website|portfolio|github|personal.?(site|url)/ },
  ];
  const SENSITIVE = /card|cc-?(num|csc|exp)|cvv|cvc|security.?code|ssn|social.?security|password|passcode|\bpin\b|routing|account.?(num|no)/;
  const SKIP_TYPES = new Set([
    "password", "hidden", "submit", "button", "reset", "image", "file", "checkbox", "radio", "range", "color",
  ]);

  const values = { ...profile };
  if (!values.fullName && (values.firstName || values.lastName)) {
    values.fullName = [values.firstName, values.lastName].filter(Boolean).join(" ");
  }

  const labelText = (el) => {
    const parts = [];
    if (el.labels) for (const l of el.labels) parts.push(l.innerText);
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      for (const id of labelledBy.split(/\s+/)) {
        const ref = document.getElementById(id);
        if (ref) parts.push(ref.innerText);
      }
    }
    return parts.join(" ");
  };

  const hintsFor = (el) =>
    [
      el.getAttribute("autocomplete"),
      el.name,
      el.id,
      el.getAttribute("placeholder"),
      el.getAttribute("aria-label"),
      labelText(el),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };

  const matchRule = (el, hints) => {
    const autocomplete = (el.getAttribute("autocomplete") || "").toLowerCase().split(/\s+/);
    for (const rule of RULES) {
      if (rule.autocomplete.some((token) => autocomplete.includes(token))) return rule.key;
    }
    for (const rule of RULES) {
      if (rule.pattern.test(hints) && !(rule.exclude && rule.exclude.test(hints))) return rule.key;
    }
    return null;
  };

  // Set the value the way a real keystroke would, so sites built with React,
  // Vue, etc. notice the change.
  const setValue = (el, value) => {
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const setSelect = (el, value) => {
    const wanted = value.trim().toLowerCase();
    const options = Array.from(el.options);
    const option =
      options.find((o) => o.value.toLowerCase() === wanted || o.text.trim().toLowerCase() === wanted) ||
      options.find((o) => o.text.trim().toLowerCase().startsWith(wanted));
    if (!option) return false;
    el.value = option.value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  const highlight = (el) => {
    el.style.outline = "2px solid #f5a623";
    el.style.outlineOffset = "1px";
    setTimeout(() => {
      el.style.outline = "";
      el.style.outlineOffset = "";
    }, 4000);
  };

  let filled = 0;
  let skippedSensitive = 0;
  for (const el of document.querySelectorAll("input, textarea, select")) {
    if (el.disabled || el.readOnly || !isVisible(el)) continue;
    if (el instanceof HTMLInputElement && SKIP_TYPES.has(el.type)) continue;

    const hints = hintsFor(el);
    if (SENSITIVE.test(hints) || /^cc-/.test(el.getAttribute("autocomplete") || "")) {
      skippedSensitive++;
      continue;
    }

    const key = matchRule(el, hints);
    const value = key && values[key];
    if (!value) continue;

    if (el instanceof HTMLSelectElement) {
      if (!overwrite && el.selectedIndex > 0) continue;
      if (setSelect(el, value)) {
        highlight(el);
        filled++;
      }
    } else {
      if (!overwrite && el.value) continue;
      setValue(el, value);
      highlight(el);
      filled++;
    }
  }

  return { filled, skippedSensitive };
}
