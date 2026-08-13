const MAX_QUERY_RETRIES = 2;

function responseStatus(error) {
  const status = Number(error?.response?.status);
  return Number.isFinite(status) ? status : null;
}

export function shouldRetryQuery(failureCount, error) {
  if (failureCount >= MAX_QUERY_RETRIES) return false;

  const status = responseStatus(error);
  if (status === null) return true;

  return status === 408 || status === 425 || status === 429 || status >= 500;
}

export function queryRetryDelay(attemptIndex, error) {
  const retryAfter = Number(error?.response?.headers?.["retry-after"]);
  if (Number.isFinite(retryAfter) && retryAfter >= 0) {
    return Math.min(retryAfter * 1000, 5_000);
  }
  return Math.min(500 * 2 ** attemptIndex, 2_000);
}
