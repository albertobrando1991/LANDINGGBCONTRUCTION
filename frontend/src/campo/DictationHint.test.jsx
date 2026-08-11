import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";
import DictationHint from "./DictationHint";

jest.mock("sonner", () => ({
  toast: { error: jest.fn() },
}));

test("spiega il problema quando il browser non supporta la dettatura", async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const original = window.SpeechRecognition;
  const originalWebkit = window.webkitSpeechRecognition;
  delete window.SpeechRecognition;
  delete window.webkitSpeechRecognition;
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () => {
    root.render(<DictationHint value="" onChange={jest.fn()} />);
  });
  await act(async () => {
    container.querySelector("button").click();
  });
  expect(toast.error).toHaveBeenCalledWith(
    "Dettatura non supportata da questo browser",
    expect.any(Object),
  );
  await act(async () => root.unmount());
  window.SpeechRecognition = original;
  window.webkitSpeechRecognition = originalWebkit;
});
