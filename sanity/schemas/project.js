// Sanity schema — Project
// Add this to your Sanity Studio's schema configuration.
// Each document you create here becomes a card on the Bigger Projects page.

export default {
    name: 'project',
    title: 'Project',
    type: 'document',
    orderings: [
        {
            title: 'Display Order',
            name: 'orderAsc',
            by: [{ field: 'order', direction: 'asc' }],
        },
    ],
    fields: [
        {
            name: 'title',
            title: 'Title',
            type: 'string',
            validation: Rule => Rule.required(),
        },
        {
            name: 'description',
            title: 'Description',
            type: 'text',
            rows: 3,
        },
        {
            name: 'coverImage',
            title: 'Cover Image',
            type: 'image',
            options: { hotspot: true },
        },
        {
            name: 'coverVideo',
            title: 'Cover Video',
            type: 'file',
            options: { accept: 'video/*' },
            description: 'If provided, the video plays on hover. Cover Image is used as the poster frame.',
        },
        {
            name: 'projectUrl',
            title: 'Project URL',
            type: 'url',
            description: 'External link shown on the card (e.g. https://lightspacelabs.com)',
        },
        {
            name: 'tags',
            title: 'Tags',
            type: 'array',
            of: [{ type: 'string' }],
            options: { layout: 'tags' },
        },
        {
            name: 'order',
            title: 'Display Order',
            type: 'number',
            description: 'Lower numbers appear first. Leave blank to sort by creation date.',
        },
    ],
    preview: {
        select: {
            title: 'title',
            media: 'coverImage',
        },
    },
};
