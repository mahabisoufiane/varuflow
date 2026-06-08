import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { X, Camera } from "lucide-react";

interface Props {
  onDetected: (barcode: string) => void;
  onClose: () => void;
}

export default function BarcodeScanner({ onDetected, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const readerRef = useRef<BrowserMultiFormatReader | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<string | undefined>();

  useEffect(() => {
    BrowserMultiFormatReader.listVideoInputDevices().then((devices) => {
      setCameras(devices);
      // Prefer rear camera on mobile
      const rear = devices.find((d) =>
        /back|rear|environment/i.test(d.label)
      );
      setSelectedCamera(rear?.deviceId ?? devices[0]?.deviceId);
    }).catch(() => setError("Camera access denied"));
  }, []);

  useEffect(() => {
    if (!selectedCamera || !videoRef.current) return;

    const reader = new BrowserMultiFormatReader();
    readerRef.current = reader;

    reader
      .decodeFromVideoDevice(selectedCamera, videoRef.current, (result, err) => {
        if (result) {
          onDetected(result.getText());
        } else if (err) {
          // Errors on individual frames (no barcode found) are expected — ignore
        }
      })
      .then((controls) => { stopRef.current = () => controls.stop(); })
      .catch(() => setError("Could not access camera"));

    return () => {
      stopRef.current?.();
      stopRef.current = null;
    };
  }, [selectedCamera, onDetected]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
      <div className="relative w-full max-w-sm rounded-2xl overflow-hidden bg-black shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between bg-gray-900 px-4 py-3">
          <div className="flex items-center gap-2 text-white">
            <Camera className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-semibold">Scan Barcode</span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-700 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Camera feed */}
        <div className="relative aspect-square bg-black">
          <video
            ref={videoRef}
            className="h-full w-full object-cover"
            autoPlay
            muted
            playsInline
          />
          {/* Scanning crosshair overlay */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="relative h-48 w-48">
              <div className="absolute top-0 left-0 h-8 w-8 border-t-4 border-l-4 border-emerald-400 rounded-tl-lg" />
              <div className="absolute top-0 right-0 h-8 w-8 border-t-4 border-r-4 border-emerald-400 rounded-tr-lg" />
              <div className="absolute bottom-0 left-0 h-8 w-8 border-b-4 border-l-4 border-emerald-400 rounded-bl-lg" />
              <div className="absolute bottom-0 right-0 h-8 w-8 border-b-4 border-r-4 border-emerald-400 rounded-br-lg" />
              {/* Animated scan line */}
              <div className="absolute left-2 right-2 top-1/2 h-0.5 bg-emerald-400/70 animate-pulse" />
            </div>
          </div>

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70">
              <p className="text-center text-sm text-red-400 px-6">{error}</p>
            </div>
          )}
        </div>

        {/* Camera selector (if multiple cameras) */}
        {cameras.length > 1 && (
          <div className="bg-gray-900 px-4 py-3">
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value)}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-white border border-gray-700"
            >
              {cameras.map((c) => (
                <option key={c.deviceId} value={c.deviceId}>
                  {c.label || `Camera ${cameras.indexOf(c) + 1}`}
                </option>
              ))}
            </select>
          </div>
        )}

        <p className="bg-gray-900 pb-4 text-center text-xs text-gray-500">
          Point at a barcode — it will be detected automatically
        </p>
      </div>
    </div>
  );
}
