const form = document.getElementById("profile");
const fillButton = document.getElementById("fill");
const overwriteBox = document.getElementById("overwrite");
const statusEl = document.getElementById("status");
const profileSection = document.getElementById("profileSection");

const readProfile = () => {
  const profile = {};
  for (const input of form.elements) {
    if (input.name) profile[input.name] = input.value.trim();
  }
  return profile;
};

const showStatus = (text, isError = false) => {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
};

// Load saved details. Open the details section if nothing is saved yet.
chrome.storage.local.get({ profile: {}, overwrite: false }).then(({ profile, overwrite }) => {
  for (const input of form.elements) {
    if (input.name && profile[input.name]) input.value = profile[input.name];
  }
  overwriteBox.checked = overwrite;
  if (!Object.values(profile).some(Boolean)) profileSection.open = true;
});

// Save on every edit, because the popup closes as soon as you click away.
form.addEventListener("input", () => chrome.storage.local.set({ profile: readProfile() }));
overwriteBox.addEventListener("change", () => chrome.storage.local.set({ overwrite: overwriteBox.checked }));

fillButton.addEventListener("click", async () => {
  const profile = readProfile();
  if (!Object.values(profile).some(Boolean)) {
    profileSection.open = true;
    showStatus("Add your details below first.", true);
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: fillPage,
      args: [profile, overwriteBox.checked],
    });
    let message = result.filled
      ? `Filled ${result.filled} field${result.filled === 1 ? "" : "s"}. Check them before you submit.`
      : "No matching empty fields found on this page.";
    if (result.skippedSensitive) message += ` Skipped ${result.skippedSensitive} sensitive field(s).`;
    showStatus(message);
  } catch (err) {
    showStatus("Can't fill this page (Chrome blocks extensions on some pages, like chrome:// and the Web Store).", true);
    console.error(err);
  }
});
