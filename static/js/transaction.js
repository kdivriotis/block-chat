// Get DOM elements related to form
const form = document.getElementById("transactionForm");
const transactionTypeButtons = document.querySelectorAll(
  'input[name="type-options"]'
);
const inputRecipient = document.getElementById("inputRecipient");
const inputAmount = document.getElementById("inputAmount");
const amountFeeDisplay = document.getElementById("amountFee");
const inputMessage = document.getElementById("inputMessage");
const messageCostDisplay = document.getElementById("messageCost");
const sendButton = document.querySelector(".send-transaction-btn");

let transactionType = "coins";

/**
 * Only shows related fields according to the selected transaction type
 *
 * @param selectedType {"coins" | "message" | "stake"}
 */
const showFormFields = (selectedType) => {
  switch (selectedType) {
    case "coins":
      inputRecipient.parentElement.classList.remove("d-none");
      inputAmount.parentElement.classList.remove("d-none");
      amountFeeDisplay.classList.remove("d-none");
      inputMessage.parentElement.classList.add("d-none");
      transactionType = "coins";
      break;
    case "stake":
      inputRecipient.parentElement.classList.add("d-none");
      inputAmount.parentElement.classList.remove("d-none");
      amountFeeDisplay.classList.add("d-none");
      inputMessage.parentElement.classList.add("d-none");
      transactionType = "stake";
      break;
    case "message":
      inputRecipient.parentElement.classList.remove("d-none");
      inputAmount.parentElement.classList.add("d-none");
      inputMessage.parentElement.classList.remove("d-none");
      transactionType = "message";
      break;
    default:
      inputRecipient.parentElement.classList.add("d-none");
      inputAmount.parentElement.classList.add("d-none");
      inputMessage.parentElement.classList.add("d-none");
      transactionType = "";
  }
  sendButton.disabled = !validateFormFields();
};

/**
 * Sets the message's cost depending on number of characters
 * and BCC fee per character
 */
const setMessageCost = () => {
  const message = inputMessage.value;
  const messageCost = message.length * bccPerChar;
  messageCostDisplay.innerHTML = `Cost: ${messageCost} BCC`;
};

/**
 * Sets the message's cost depending on number of characters
 * and BCC fee per character
 */
const setAmountFee = () => {
  const amount = parseFloat(inputAmount.value);
  let fee = 0.0;
  if (!isNaN(amount)) fee = (transferFee / 100.0) * amount;

  amountFeeDisplay.innerHTML = `An extra ${transferFee} % (${fee.toFixed(
    2
  )} BCC) will be charged`;
};

/**
 * Validate selected recipient.
 * Recipient's public key has to exist inside given list of public keys.
 *
 * @returns {string | null} error message (string) in case of invalid string, otherwise null
 */
const validateRecipient = () => {
  const recipient = inputRecipient.value;
  if (!recipient || recipient.trim().length === 0)
    return "This field cannot be empty";

  const index = publicKeys.findIndex((key) => key === recipient);
  if (index == -1) return "Select a valid recipient from the list";

  return null;
};

/**
 * Validate message.
 * Message has to include at least one character, and cannot
 * exceed the amount of characters allowed based on the node's
 * available coins.
 *
 * @returns {string | null} error message (string) in case of invalid string, otherwise null
 */
const validateMessage = () => {
  const message = inputMessage.value;
  if (!message || message.trim().length === 0)
    return "This field cannot be empty";

  const messageCost = message.length * bccPerChar;
  if (messageCost > coins)
    return `Your balance allows maximum ${Math.floor(
      coins / bccPerChar
    )} characters`;

  return null;
};

/**
 * Validate coins amount.
 * The input field needs to be a valid (positive) number, that
 * does not exceed node's available coins.
 *
 * @returns {string | null} error message (string) in case of invalid string, otherwise null
 */
const validateCoins = () => {
  const amountStr = inputAmount.value;
  if (!amountStr) return "This field cannot be empty";

  const amount = parseFloat(amountStr);
  if (isNaN(amount)) return "Please enter a number";

  if (amount <= 0) return "Amount should be a positive number";

  const fee = (transferFee / 100.0) * amount;
  const totalAmount = amount + fee;
  if (totalAmount > coins - stake)
    return `Total amount ${totalAmount} BCC exceeds your available balance`;

  return null;
};

/**
 * Validate stake amount.
 * The input field needs to be a valid (non-negative) number, that
 * does not exceed node's total coins.
 *
 * @returns {string | null} error message (string) in case of invalid string, otherwise null
 */
const validateStake = () => {
  const amountStr = inputAmount.value;
  if (!amountStr) return "This field cannot be empty";

  const amount = parseFloat(amountStr);
  if (isNaN(amount)) return "Please enter a number";

  if (amount < 0) return "Amount should be a non-negative number";

  if (amount > coins) return `Stake amount ${amount} BCC exceeds your balance`;

  return null;
};

/**
 * Check the validity of a form field element
 * @param {HTMLInputElement | HTMLTextAreaElement} field The input or textarea field to be checked
 * @param {boolean} checkOnly If true, only check validity without updating the error message
 * @return true or false, depending on whether the field is valid or not
 *
 */
const validateFormField = (field, checkOnly = false) => {
  let errorString = null;
  switch (field.id) {
    case "inputRecipient":
      errorString = validateRecipient();
      break;
    case "inputAmount":
      if (transactionType == "coins") errorString = validateCoins();
      else errorString = validateStake();
      break;
    case "inputMessage":
      errorString = validateMessage();
      break;
    default:
      return false;
  }

  if (checkOnly) return errorString == null;

  const errorField = field.nextElementSibling;
  if (!!errorString && field.value.length > 0) {
    field.classList.add("is-invalid");
    errorField.textContent = errorString;
  } else {
    field.classList.remove("is-invalid");
    errorField.textContent = "";
  }

  return errorString == null;
};

/**
 * Validate all form elements on contact page
 * @param {boolean} checkOnly If true, only check validity without updating the error message
 * @return true or false, depending on whether all form fields are valid or not
 */
const validateFormFields = (checkOnly = false) => {
  let isValid = true;
  switch (transactionType) {
    case "coins":
      return (
        validateFormField(inputRecipient, checkOnly) &&
        validateFormField(inputAmount, checkOnly)
      );
    case "message":
      return (
        validateFormField(inputRecipient, checkOnly) &&
        validateFormField(inputMessage, checkOnly)
      );
    case "stake":
      return validateFormField(inputAmount, checkOnly);
    default:
      return false;
  }
};

/**
 * Create all event listeners
 */

// Transaction Type Radio Selection
for (const btn of transactionTypeButtons) {
  btn.addEventListener("change", (event) => {
    const selectedValue = event.target.value;
    showFormFields(selectedValue);
  });
}

// Recipient dropdown selection
inputRecipient.addEventListener("change", (event) => {
  console.log(event.target.value);
});

// Amount input
inputAmount.addEventListener("input", () => {
  setAmountFee();
  sendButton.disabled = !validateFormFields(true);
});

inputAmount.addEventListener("blur", () => {
  setAmountFee();
  sendButton.disabled = !validateFormFields();
});

// Message input
inputMessage.addEventListener("input", () => {
  setMessageCost();
  sendButton.disabled = !validateFormFields(true);
});

inputMessage.addEventListener("blur", () => {
  setMessageCost();
  sendButton.disabled = !validateFormFields();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Return and disable the submit button if form is not valid
  if (!validateFormFields()) {
    sendButton.disabled = true;
    return;
  }

  const recipient = transactionType !== "stake" ? inputRecipient.value : "0";
  const amount =
    transactionType !== "message" ? parseFloat(inputAmount.value) : 0.0;
  const message =
    transactionType === "message" ? inputMessage.value.trim() : "";

  const transactionBody = { type: transactionType, recipient, amount, message };

  const responseToast = document.querySelector("#responseToast");
  const toastBootstrap = bootstrap.Toast.getOrCreateInstance(responseToast);
  const toastBody = document.querySelector(".toast-body");

  try {
    sendButton.disabled = true;
    const response = await fetch("/transaction", {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(transactionBody),
    });

    const content = await response.json();

    if (response.ok) {
      toastBody.innerHTML = `&#x2713; ${content.message}`;
      responseToast.classList.add("text-bg-success");
      responseToast.classList.remove("text-bg-danger");
      form.reset();
    } else {
      toastBody.innerHTML = `X ${content.message}`;
      responseToast.classList.add("text-bg-danger");
      responseToast.classList.remove("text-bg-success");
    }
  } catch (err) {
    toastBody.innerHTML = "X Something went wrong";
    responseToast.classList.add("toast-bg-danger");
    responseToast.classList.remove("text-bg-success");
  }
  toastBootstrap.show();
  validateFormFields();

  // Clear the toast message after 3 seconds
  setTimeout(() => {
    toastBootstrap.hide();
  }, 3000);

  setTimeout(() => {
    location.reload();
  }, 4000);
});

/**
 * On page load
 */
window.addEventListener("load", () => {
  for (const btn of transactionTypeButtons)
    if (btn.checked) showFormFields(btn.value);

  setMessageCost();
  setAmountFee();
  sendButton.disabled = !validateFormFields();
});
