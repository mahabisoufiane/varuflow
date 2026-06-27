import { PageSkeleton } from 'varuflow-ui';

export function Default() {
  return <PageSkeleton />;
}

export function FewRows() {
  return <PageSkeleton rows={3} />;
}

export function ManyRows() {
  return <PageSkeleton rows={8} />;
}
