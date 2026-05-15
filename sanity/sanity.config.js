import { defineConfig } from 'sanity'
import { structureTool } from 'sanity/structure'
import { visionTool } from '@sanity/vision'
import project from './schemas/project'

export default defineConfig({
    name: 'thetinytasks',
    title: 'The Tiny Tasks',
    projectId: 'mcp0g14m',
    dataset: 'production',
    plugins: [structureTool(), visionTool()],
    schema: {
        types: [project],
    },
})
