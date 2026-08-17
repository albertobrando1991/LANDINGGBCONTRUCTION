import { downloadBlob } from "./downloadBlob";

describe("downloadBlob", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    URL.createObjectURL = jest.fn(() => "blob:contratto-test");
    URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  test("mantiene valido l'URL finche il browser ha avviato il download", () => {
    const click = jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    downloadBlob(new Blob(["pdf"]), "contratto.pdf");

    expect(click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    expect(document.querySelector('a[href="blob:contratto-test"]')).toBeNull();

    jest.advanceTimersByTime(60000);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:contratto-test");
    click.mockRestore();
  });
});
