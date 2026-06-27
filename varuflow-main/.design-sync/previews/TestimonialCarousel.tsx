import { TestimonialCarousel } from 'varuflow-ui';

const testimonials = [
  {
    quote: "We replaced Fortnox and an Excel inventory sheet with Varuflow in a single afternoon. Our invoicing errors dropped to near-zero within the first week.",
    author: "Anna Lindqvist",
    role: "CEO",
    company: "Nordisk Grossist AB",
    initials: "AL",
  },
  {
    quote: "The BankID login and Swedish BAS chart of accounts were already built in. Our accountant was impressed — no manual mapping required.",
    author: "Erik Bergström",
    role: "CFO",
    company: "ScandiTrade Import",
    initials: "EB",
  },
  {
    quote: "Customer support is genuinely fast. We had a question about multi-currency invoicing on a Friday afternoon and got a real answer within 20 minutes.",
    author: "Maria Haugen",
    role: "Operations Manager",
    company: "Bergen Supply AS",
    initials: "MH",
  },
];

export function Default() {
  return (
    <div style={{ padding: '40px 24px', background: '#0d1526', borderRadius: '12px' }}>
      <TestimonialCarousel testimonials={testimonials} />
    </div>
  );
}

export function Single() {
  return (
    <div style={{ padding: '40px 24px', background: '#0d1526', borderRadius: '12px' }}>
      <TestimonialCarousel testimonials={[testimonials[0]]} />
    </div>
  );
}
