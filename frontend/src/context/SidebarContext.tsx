"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

interface SidebarContextType {
  collapsed: boolean;
  toggleSidebar: () => void;
  setCollapsed: (collapsed: boolean) => void;
}

const SidebarContext = createContext<SidebarContextType>({
  collapsed: false,
  toggleSidebar: () => {},
  setCollapsed: () => {},
});

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("ocr_sidebar_collapsed");
      if (saved !== null) {
        setCollapsed(saved === "true");
      }
    } catch (e) {
      // Ignorar errores de localStorage
    }
  }, []);

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("ocr_sidebar_collapsed", String(next));
      } catch (e) {}
      return next;
    });
  };

  const handleSetCollapsed = (val: boolean) => {
    setCollapsed(val);
    try {
      localStorage.setItem("ocr_sidebar_collapsed", String(val));
    } catch (e) {}
  };

  return (
    <SidebarContext.Provider
      value={{
        collapsed,
        toggleSidebar,
        setCollapsed: handleSetCollapsed,
      }}
    >
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  return useContext(SidebarContext);
}
