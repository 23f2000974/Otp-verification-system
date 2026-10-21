"use strict";

const emailForm = document.querySelector("#email-form");
const codeForm = document.querySelector("#code-form");
const emailInput = document.querySelector("#email");
const codeInput = document.querySelector("#code");
const message = document.querySelector("#message");
const sentEmail = document.querySelector("#sent-email");
const resendButton = document.querySelector("#resend");
const resendCountdown = document.querySelector("#resend-countdown");
const changeEmailButton = document.querySelector("#change-email");
const stepDescription = document.querySelector("#step-description");
const stepOne = document.querySelector("#step-one");
const stepTwo = document.querySelector("#step-two");
const codeLabel = document.querySelector("label[for='code']");

let challengeId = null;
let emailAddress = "";
let resendTimer = null;

function showMessage(text, success = false) {
  message.textContent = text;
  message.classList.toggle("success", success);
  message.hidden = false;
}

function clearMessage() {
  message.hidden = true;
  message.textContent = "";
  message.classList.remove("success");
}

function setBusy(form, busy) {
  for (const button of form.querySelectorAll("button[type='submit']")) {
    button.disabled = busy;
  }
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "same-origin",
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.detail || "Something went wrong. Please try again.");
    error.retryAfter = Number(response.headers.get("Retry-After")) || 0;
    throw error;
  }
  return result;
}

function startResendCountdown(seconds) {
  window.clearInterval(resendTimer);
  let remaining = Math.max(0, seconds);
  resendButton.disabled = remaining > 0;
  resendCountdown.textContent = remaining > 0 ? `(${remaining}s)` : "";
  if (remaining === 0) return;
  resendTimer = window.setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      window.clearInterval(resendTimer);
      resendCountdown.textContent = "";
      resendButton.disabled = false;
      return;
    }
    resendCountdown.textContent = `(${remaining}s)`;
  }, 1000);
}

async function sendCode() {
  clearMessage();
  setBusy(emailForm, true);
  resendButton.disabled = true;
  try {
    const result = await requestJson("/api/v1/challenges", { email: emailAddress });
    challengeId = result.challenge_id;
    codeInput.value = "";
    emailForm.classList.add("hidden");
    codeForm.classList.remove("hidden");
    sentEmail.textContent = emailAddress;
    const expiresInMinutes = Math.ceil(result.expires_in_seconds / 60);
    const minuteLabel = expiresInMinutes === 1 ? "minute" : "minutes";
    stepDescription.textContent =
      `Enter the one-time code from your email. It expires in ${expiresInMinutes} ${minuteLabel}.`;
    stepOne.classList.add("complete");
    stepOne.classList.remove("active");
    stepTwo.classList.add("active");
    showMessage("Your verification code is on its way.", true);
    codeInput.focus();
    startResendCountdown(result.retry_after_seconds);
  } catch (error) {
    const detail = error.message === "Email delivery is not configured."
      ? "Email delivery is not configured. Set SMTP_HOST and SMTP credentials in .env, then restart the server."
      : error.message;
    showMessage(detail);
    startResendCountdown(error.retryAfter);
  } finally {
    setBusy(emailForm, false);
  }
}

emailForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();
  if (!emailInput.reportValidity()) return;
  emailAddress = emailInput.value.trim();
  await sendCode();
});

resendButton.addEventListener("click", sendCode);

codeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();
  if (!codeInput.reportValidity()) return;
  setBusy(codeForm, true);
  let completed = false;
  try {
    await requestJson(
      `/api/v1/challenges/${encodeURIComponent(challengeId)}/verify`,
      { email: emailAddress, code: codeInput.value },
    );
    showMessage("Your email has been verified successfully.", true);
    completed = true;
    codeInput.disabled = true;
    resendButton.disabled = true;
    changeEmailButton.disabled = true;
    stepTwo.classList.add("complete");
    stepTwo.classList.remove("active");
    stepDescription.textContent = "Your email address is verified and ready to use.";
  } catch (error) {
    showMessage(error.message);
    if (error.retryAfter) startResendCountdown(error.retryAfter);
  } finally {
    setBusy(codeForm, completed);
  }
});

changeEmailButton.addEventListener("click", () => {
  window.clearInterval(resendTimer);
  challengeId = null;
  emailAddress = "";
  codeInput.value = "";
  codeInput.disabled = false;
  emailInput.value = "";
  emailForm.classList.remove("hidden");
  codeForm.classList.add("hidden");
  stepOne.classList.remove("complete");
  stepOne.classList.add("active");
  stepTwo.classList.remove("active", "complete");
  stepDescription.textContent = "Enter your email and we’ll send you a one-time verification code.";
  clearMessage();
  emailInput.focus();
});

fetch("/api/v1/config", { credentials: "same-origin" })
  .then((response) => {
    if (!response.ok) throw new Error("Could not load verification settings.");
    return response.json();
  })
  .then(({ otp_length }) => {
    codeInput.minLength = otp_length;
    codeInput.maxLength = otp_length;
    codeInput.pattern = `[0-9]{${otp_length}}`;
    codeInput.placeholder = "•".repeat(otp_length);
    codeLabel.textContent = `${otp_length}-digit verification code`;
  })
  .catch(() => showMessage("Verification is temporarily unavailable. Please refresh and try again."));
