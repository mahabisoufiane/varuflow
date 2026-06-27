// LogoCloud — customer logo grid. Uses text placeholders until real logo assets are available.
interface Logo {
  name: string;
  description?: string;
}

interface LogoCloudProps {
  title?: string;
  logos?: Logo[];
}

const DEFAULT_LOGOS: Logo[] = [
  { name: "Nordisk Grossist AB", description: "Wholesale distributor, Sweden" },
  { name: "Lagerhaus Nordic", description: "Retail & wholesale" },
  { name: "ScandiTrade", description: "B2B importer" },
  { name: "Malmö Handel", description: "Regional distributor" },
  { name: "Stockholm Supply", description: "E-commerce wholesale" },
  { name: "Göteborg Parts", description: "Industrial parts" },
];

export default function LogoCloud({ title = "Trusted by growing Nordic businesses", logos = DEFAULT_LOGOS }: LogoCloudProps) {
  return (
    <section className="py-16 px-4">
      <p className="vf-text-m mb-10 text-center text-xs font-semibold uppercase tracking-widest">
        {title}
      </p>
      <div className="mx-auto grid max-w-4xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {logos.map((logo) => (
          <div
            key={logo.name}
            title={logo.description}
            className="flex h-14 items-center justify-center rounded-xl border border-white/8 bg-white/4 px-3"
          >
            <span className="text-center text-xs font-semibold text-slate-500 leading-tight">
              {logo.name}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
