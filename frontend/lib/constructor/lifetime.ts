export type ConstructorLifetime = { account: string | null; revision: number };

/** Guest work may be adopted once; ending an authenticated lifetime revokes it. */
export function nextConstructorLifetime(
  previous: ConstructorLifetime,
  account: string | null,
): ConstructorLifetime {
  if (previous.account === account) return previous;
  return {
    account,
    revision: previous.revision + (previous.account === null ? 0 : 1),
  };
}
