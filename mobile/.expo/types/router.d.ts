/* eslint-disable */
import * as Router from 'expo-router';

export * from 'expo-router';

declare module 'expo-router' {
  export namespace ExpoRouter {
    export interface __routes<T extends string = string> extends Record<string, unknown> {
      StaticRoutes: `/` | `/(app)` | `/(app)/analytics` | `/(app)/dashboard` | `/(app)/inventory` | `/(app)/settings` | `/(auth)/login` | `/(auth)/signup` | `/_sitemap` | `/analytics` | `/dashboard` | `/inventory` | `/login` | `/settings` | `/signup`;
      DynamicRoutes: never;
      DynamicRouteTemplate: never;
    }
  }
}
