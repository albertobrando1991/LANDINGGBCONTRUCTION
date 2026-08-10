import { jsPDF } from "jspdf";
import {
  downloadRilievoPdf,
  downloadRilievoPng,
  rilievoExportBaseName,
  rilievoExportDimensions,
} from "./rilievoExport";

jest.mock("jspdf", () => ({ jsPDF: jest.fn() }));

test("genera un elaborato ad alta risoluzione mantenendo le proporzioni", () => {
  expect(rilievoExportDimensions(1200, 800)).toEqual({
    width: 2000,
    height: 1333,
  });
  expect(rilievoExportDimensions(800, 1200)).toEqual({
    width: 1333,
    height: 2000,
  });
});

test("crea un nome file sicuro dalla planimetria salvata", () => {
  expect(rilievoExportBaseName("Pianta Città - Piano 1.PDF", "ignored")).toBe(
    "pianta-citta-piano-1",
  );
  expect(
    rilievoExportBaseName("", "ab35adfc-2a06-43f9-b8d5-39c3df128b78"),
  ).toBe("rilievo-ab35adfc");
});

test("scarica il canvas annotato come immagine PNG", async () => {
  const previousCreateObjectURL = URL.createObjectURL;
  const previousRevokeObjectURL = URL.revokeObjectURL;
  const click = jest
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  const timeout = jest
    .spyOn(window, "setTimeout")
    .mockImplementation((callback) => callback());
  URL.createObjectURL = jest.fn(() => "blob:rilievo");
  URL.revokeObjectURL = jest.fn();
  const canvas = {
    toBlob: (callback) => callback(new Blob(["png"], { type: "image/png" })),
  };

  await downloadRilievoPng(canvas, "pianta-test");

  expect(URL.createObjectURL).toHaveBeenCalled();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:rilievo");
  expect(click).toHaveBeenCalled();
  click.mockRestore();
  timeout.mockRestore();
  URL.createObjectURL = previousCreateObjectURL;
  URL.revokeObjectURL = previousRevokeObjectURL;
});

test("genera il PDF nella stessa proporzione del canvas", async () => {
  const addImage = jest.fn();
  const save = jest.fn();
  jsPDF.mockImplementation(() => ({
    internal: {
      pageSize: {
        getWidth: () => 2000,
        getHeight: () => 1333,
      },
    },
    addImage,
    save,
  }));
  const canvas = {
    width: 2000,
    height: 1333,
    toDataURL: jest.fn(() => "data:image/jpeg;base64,annotata"),
  };

  await downloadRilievoPdf(canvas, "pianta-test");

  expect(addImage).toHaveBeenCalledWith(
    "data:image/jpeg;base64,annotata",
    "JPEG",
    0,
    0,
    2000,
    1333,
    undefined,
    "FAST",
  );
  expect(save).toHaveBeenCalledWith("pianta-test-annotata.pdf");
});
