import { defineConfig } from "sanity";
import { structureTool } from "sanity/structure";
import { visionTool } from "@sanity/vision";
import { schemaTypes } from "./schemas";

const projectId = process.env.SANITY_STUDIO_PROJECT_ID!;
const dataset = process.env.SANITY_STUDIO_DATASET ?? "production";

export default defineConfig({
  name: "varuflow-studio",
  title: "Varuflow Blog",
  projectId,
  dataset,
  plugins: [
    structureTool({
      structure: (S) =>
        S.list()
          .title("Content")
          .items([
            S.listItem()
              .title("Blog posts")
              .child(
                S.documentTypeList("post")
                  .title("Blog posts")
                  .filter('_type == "post"')
              ),
            S.listItem()
              .title("Authors")
              .child(S.documentTypeList("author").title("Authors")),
            S.listItem()
              .title("Categories")
              .child(S.documentTypeList("category").title("Categories")),
            S.listItem()
              .title("Tags")
              .child(S.documentTypeList("tag").title("Tags")),
          ]),
    }),
    visionTool(),
  ],
  schema: {
    types: schemaTypes,
  },
});
