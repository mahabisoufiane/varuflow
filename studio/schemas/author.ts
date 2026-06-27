import { defineField, defineType } from "sanity";
import { UserIcon } from "@sanity/icons";

export default defineType({
  name: "author",
  title: "Author",
  type: "document",
  icon: UserIcon,
  fields: [
    defineField({ name: "name", type: "string", title: "Name", validation: (R) => R.required() }),
    defineField({ name: "slug", type: "slug", title: "Slug", options: { source: "name" } }),
    defineField({ name: "role", type: "string", title: "Role / Title" }),
    defineField({
      name: "bio",
      type: "text",
      title: "Bio",
      rows: 3,
    }),
    defineField({
      name: "photo",
      type: "image",
      title: "Profile photo",
      options: { hotspot: true },
    }),
    defineField({ name: "twitter", type: "url", title: "Twitter / X URL" }),
    defineField({ name: "linkedin", type: "url", title: "LinkedIn URL" }),
  ],
  preview: {
    select: { title: "name", subtitle: "role", media: "photo" },
  },
});
