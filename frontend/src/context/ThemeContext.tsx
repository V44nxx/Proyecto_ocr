"use client";

import React, { createContext, useContext, useEffect, useState, useRef } from "react";

export type Theme = "dark" | "light";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: (event?: React.MouseEvent | MouseEvent | { clientX: number; clientY: number }) => void;
  setTheme: (t: Theme, coords?: { clientX: number; clientY: number }) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "dark",
  toggleTheme: () => {},
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);
  const isTransitioningRef = useRef(false);

  useEffect(() => {
    try {
      const savedTheme = (localStorage.getItem("ocr_theme") as Theme) || "dark";
      setThemeState(savedTheme);
      applyTheme(savedTheme);
    } catch {
      applyTheme("dark");
    } finally {
      setMounted(true);
    }
  }, []);

  const applyTheme = (newTheme: Theme) => {
    const root = document.documentElement;
    if (newTheme === "light") {
      root.classList.add("light");
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    } else {
      root.classList.add("dark");
      root.classList.remove("light");
      root.setAttribute("data-theme", "dark");
    }
  };

  const setTheme = (newTheme: Theme, coords?: { clientX: number; clientY: number }) => {
    if (isTransitioningRef.current) return;
    try {
      localStorage.setItem("ocr_theme", newTheme);
    } catch {}

    if (typeof document === "undefined") {
      setThemeState(newTheme);
      return;
    }

    const root = document.documentElement;

    // Verificar si el navegador soporta View Transitions de forma nativa
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const hasViewTransition =
      "startViewTransition" in document &&
      typeof (document as any).startViewTransition === "function" &&
      !prefersReducedMotion;

    if (hasViewTransition) {
      isTransitioningRef.current = true;

      // Calcular origen del destello radial
      let x = coords?.clientX;
      let y = coords?.clientY;
      if (x === undefined || y === undefined) {
        const toggleBtn = document.querySelector('button[title*="Modo"]');
        if (toggleBtn) {
          const rect = toggleBtn.getBoundingClientRect();
          x = rect.left + rect.width / 2;
          y = rect.top + rect.height / 2;
        } else {
          x = window.innerWidth / 2;
          y = window.innerHeight / 2;
        }
      }

      const endRadius = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      );

      // Fijar variables CSS del centro para que el clip-path inicial sea exactamente 0px
      // Esto elimina el flasheo de 1 frame al iniciar la transición.
      root.style.setProperty("--theme-x", `${x}px`);
      root.style.setProperty("--theme-y", `${y}px`);
      root.classList.add("theme-transitioning");

      const transition = (document as any).startViewTransition(() => {
        applyTheme(newTheme);
        setThemeState(newTheme);
      });

      transition.ready
        .then(() => {
          try {
            const anim = (document.documentElement as any).animate(
              {
                clipPath: [
                  `circle(0px at ${x}px ${y}px)`,
                  `circle(${endRadius}px at ${x}px ${y}px)`,
                ],
              },
              {
                duration: 480,
                easing: "cubic-bezier(0.16, 1, 0.3, 1)",
                pseudoElement: "::view-transition-new(root)",
              }
            );
            return anim?.finished;
          } catch {
            return undefined;
          }
        })
        .catch(() => {});

      // Esperar a que la transición termine completamente en el navegador antes de limpiar
      transition.finished
        .catch(() => {})
        .finally(() => {
          root.classList.remove("theme-transitioning");
          root.style.removeProperty("--theme-x");
          root.style.removeProperty("--theme-y");
          isTransitioningRef.current = false;
        });
    } else {
      // Fallback controlado para navegadores sin View Transitions:
      // Se sincronizan todas las transiciones simultáneamente para evitar desfases
      root.classList.add("theme-sync-transition");
      applyTheme(newTheme);
      setThemeState(newTheme);
      setTimeout(() => {
        root.classList.remove("theme-sync-transition");
        isTransitioningRef.current = false;
      }, 350);
    }
  };

  const toggleTheme = (event?: React.MouseEvent | MouseEvent | { clientX: number; clientY: number }) => {
    const next = theme === "dark" ? "light" : "dark";
    const coords =
      event && "clientX" in event && "clientY" in event
        ? { clientX: event.clientX, clientY: event.clientY }
        : undefined;
    setTheme(next, coords);
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
