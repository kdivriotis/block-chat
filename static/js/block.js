document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") {
    const previousBlock = document.getElementById("previousBlockLink");
    if (previousBlock) {
      previousBlock.click();
    }
    // Your code for left arrow key press
  } else if (event.key === "ArrowRight") {
    const nextBlock = document.getElementById("nextBlockLink");
    if (nextBlock) {
      nextBlock.click();
    }
  }
});
