/**
 * NotificationContext — app-wide toasts and confirm dialogs.
 *
 * Replaces native alert()/confirm() and scattered inline error text with a
 * single, themed feedback channel:
 *   const toast = useToast();      toast.success('Job deleted.');
 *   const confirm = useConfirm();  if (await confirm({ ... })) { ... }
 *
 * Self-contained (no external deps) so it matches the navy theme and adds no
 * bundle weight beyond a few KB.
 */
import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import CheckCircle from '../components/icons/CheckCircle';
import XCircle from '../components/icons/XCircle';
import AlertCircle from '../components/icons/AlertCircle';

type ToastType = 'success' | 'error' | 'info';
interface Toast {
  id: number;
  type: ToastType;
  message: string;
}
interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}
type ConfirmApi = (opts: ConfirmOptions) => Promise<boolean>;

const ToastCtx = createContext<ToastApi | null>(null);
const ConfirmCtx = createContext<ConfirmApi | null>(null);

const TOAST_STYLE: Record<ToastType, { cls: string; icon: React.ReactNode }> = {
  success: { cls: 'border-green-200', icon: <CheckCircle className="w-5 h-5 text-green-600 shrink-0" /> },
  error: { cls: 'border-red-200', icon: <XCircle className="w-5 h-5 text-red-600 shrink-0" /> },
  info: { cls: 'border-navy-200', icon: <AlertCircle className="w-5 h-5 text-navy-600 shrink-0" /> },
};

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmState, setConfirmState] = useState<ConfirmOptions | null>(null);
  const idRef = useRef(0);
  const resolverRef = useRef<((v: boolean) => void) | null>(null);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (type: ToastType, message: string) => {
      const id = (idRef.current += 1);
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss]
  );

  const toastApi = useMemo<ToastApi>(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push]
  );

  const confirm = useCallback<ConfirmApi>((opts) => {
    setConfirmState(opts);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const closeConfirm = useCallback((result: boolean) => {
    setConfirmState(null);
    if (resolverRef.current) {
      resolverRef.current(result);
      resolverRef.current = null;
    }
  }, []);

  return (
    <ToastCtx.Provider value={toastApi}>
      <ConfirmCtx.Provider value={confirm}>
        {children}

        {/* Toasts */}
        <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 w-[min(92vw,360px)]" aria-live="polite">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`flex items-start gap-2.5 bg-white border ${TOAST_STYLE[t.type].cls} rounded-lg shadow-lg px-3.5 py-2.5 text-sm text-gray-800`}
            >
              {TOAST_STYLE[t.type].icon}
              <span className="flex-1 leading-snug">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="text-gray-400 hover:text-gray-700 leading-none text-lg -mt-0.5"
              >
                ×
              </button>
            </div>
          ))}
        </div>

        {/* Confirm dialog */}
        {confirmState && (
          <div
            className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/40 px-4"
            role="dialog"
            aria-modal="true"
            onClick={() => closeConfirm(false)}
          >
            <div
              className="bg-white rounded-xl shadow-2xl max-w-sm w-full p-5"
              onClick={(e) => e.stopPropagation()}
            >
              {confirmState.title && (
                <h3 className="text-base font-semibold text-gray-900 mb-1.5">{confirmState.title}</h3>
              )}
              <p className="text-sm text-gray-600">{confirmState.message}</p>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  onClick={() => closeConfirm(false)}
                  className="px-4 py-2 rounded-md text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 transition"
                >
                  {confirmState.cancelLabel || 'Cancel'}
                </button>
                <button
                  onClick={() => closeConfirm(true)}
                  className={`px-4 py-2 rounded-md text-sm font-medium text-white transition ${
                    confirmState.danger
                      ? 'bg-red-600 hover:bg-red-700'
                      : 'bg-navy-600 hover:bg-navy-800'
                  }`}
                >
                  {confirmState.confirmLabel || 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        )}
      </ConfirmCtx.Provider>
    </ToastCtx.Provider>
  );
};

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error('useToast must be used within NotificationProvider');
  return ctx;
}

export function useConfirm(): ConfirmApi {
  const ctx = useContext(ConfirmCtx);
  if (!ctx) throw new Error('useConfirm must be used within NotificationProvider');
  return ctx;
}
