import { createRafScheduler } from "./rafScheduler";

test("coalescizza piu richieste nello stesso frame", () => {
  const draw = jest.fn();
  let callback;
  const raf = jest.fn((next) => {
    callback = next;
    return 17;
  });
  const scheduler = createRafScheduler(draw, raf, jest.fn());

  scheduler.schedule();
  scheduler.schedule();
  scheduler.schedule();
  expect(raf).toHaveBeenCalledTimes(1);
  callback();
  expect(draw).toHaveBeenCalledTimes(1);
  scheduler.schedule();
  expect(raf).toHaveBeenCalledTimes(2);
});

test("annulla il frame pendente", () => {
  const cancel = jest.fn();
  const scheduler = createRafScheduler(jest.fn(), () => 9, cancel);
  scheduler.schedule();
  scheduler.cancel();
  expect(cancel).toHaveBeenCalledWith(9);
});
