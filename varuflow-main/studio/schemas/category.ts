import { defineField, defineType } from "sanity";
import { TagIcon } from "@sanity/icons";

export default defineType({
  name: "category",
  title: "Category",
  type: "document",
  icon: TagIcon,
  fields: [
    defineField({
      name: "title",
      type: "string",
      title: "Title",
      validation: (R) => R.required(),
    }),
    defineField({
      name: "slug",
      type: "slug",
      title: "Slug",
      options: { source: "title" },
      validation: (R) => R.required(),
    }),
    defineField({ name: "description", type: "text", title: "Description", rows: 2 }),
  ],
  preview: { select: { title: "title", subtitle: "slug.current" } },
});
