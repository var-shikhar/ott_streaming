// Lightweight client-side session flag. Auth cookies are httpOnly (invisible to
// JS), so components can't check them directly — TopBar's /auth/me result is
// recorded here and consulted before firing authenticated requests as a guest.
let loggedIn: boolean | null = null; // null = not yet known

export function setLoggedIn(value: boolean) {
  loggedIn = value;
}

export function isLoggedIn(): boolean | null {
  return loggedIn;
}
