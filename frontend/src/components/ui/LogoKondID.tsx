/** Logotipo de KondID: muestra la versión clara u oscura según el tema activo. La altura se pasa en `className`. */
export default function LogoKondID({ className = "h-8" }: { className?: string }) {
  return (
    <>
      <img
        src="/marca/kondid-claro.png"
        alt="KondID"
        width={273}
        height={66}
        draggable={false}
        className={`${className} w-auto block dark:hidden select-none`}
      />
      <img
        src="/marca/kondid-oscuro.png"
        alt="KondID"
        width={273}
        height={66}
        draggable={false}
        className={`${className} w-auto hidden dark:block select-none`}
      />
    </>
  );
}

/** Huella del logotipo, para espacios pequeños como el menú lateral cerrado. */
export function HuellaKondID({ className = "w-8 h-8" }: { className?: string }) {
  return (
    <img
      src="/marca/kondid-huella.png"
      alt="KondID"
      width={57}
      height={57}
      draggable={false}
      className={`${className} select-none`}
    />
  );
}
