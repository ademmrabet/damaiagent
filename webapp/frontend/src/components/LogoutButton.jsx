import { logout } from '../api.js';

export default function LogoutButton() {
  return (
    <button type="button" className="logout-btn" onClick={logout}>
      Log out
    </button>
  );
}
