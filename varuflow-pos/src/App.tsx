import { useState } from "react";
import { getToken } from "./lib/auth";
import PinLogin from "./components/PinLogin";
import PosMain from "./components/PosMain";

export default function App() {
  const [authed, setAuthed] = useState(() => !!getToken());

  if (!authed) {
    return <PinLogin onSuccess={() => setAuthed(true)} />;
  }

  return <PosMain />;
}
