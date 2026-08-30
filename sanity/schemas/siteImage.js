// Sanity schema — Site Image
//
// One document per image slot on the public marketing pages.  Documents are
// created by the site admin at /admin, which writes them with a deterministic
// _id of `siteImage.<slot>` so an upload is always an upsert.
//
// The slot list must stay in sync with WSR/site_admin/slots.py — that module is
// the source of truth for which slots exist and where they render.

export const SITE_IMAGE_SLOTS = [
    { title: 'Hero background',          value: 'hero' },
    { title: 'Philosophy panel',         value: 'philosophy-panel' },
    { title: 'Sankey Chart card',        value: 'sankey-chart' },
    { title: 'Background Remover card',  value: 'background-remover' },
    { title: 'Return Stream card',       value: 'return-stream' },
    { title: 'Market Outlook card',      value: 'market-outlook' },
    { title: 'Meal Planner card',        value: 'meal-planner' },
    { title: 'About card',               value: 'about' },
    { title: 'Bigger Projects card',     value: 'bigger-projects' },
    { title: 'About portrait',           value: 'portrait' },
]

export default {
    name: 'siteImage',
    title: 'Site Image',
    type: 'document',
    fields: [
        {
            name: 'slot',
            title: 'Slot',
            type: 'string',
            description: 'Which position on the site this image fills.',
            options: { list: SITE_IMAGE_SLOTS },
            validation: Rule => Rule.required(),
        },
        {
            name: 'image',
            title: 'Image',
            type: 'image',
            options: { hotspot: true },
            validation: Rule => Rule.required(),
        },
        {
            name: 'alt',
            title: 'Alt text',
            type: 'string',
            description: 'Describes the image for screen readers. Leave blank for purely decorative images.',
        },
        {
            name: 'updatedAt',
            title: 'Last updated',
            type: 'datetime',
            readOnly: true,
        },
    ],
    preview: {
        select: { title: 'slot', media: 'image' },
    },
}
