import { defineField, defineType } from "sanity";

export default defineType({
  name: "tag",
  title: "Tag",
  type: "document",
  fields: [
    defineField({ name: "label", type: "string", title: "Label", validation: (R) => R.required() }),
    defineField({
      name: "slug",
      type: "slug",
      title: "Slug",
      options: { source: "label" },
      validation: (R) => R.required(),
    }),
  ],
  preview: { select: { title: "label" } },
});
