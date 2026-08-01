import type { StoryFn } from '@storybook/vue3-vite';

import N8nExternalLink from './ExternalLink.vue';

export default {
	title: 'Core/ExternalLink',
	component: N8nExternalLink,
	argTypes: {
		size: {
			control: 'select',
			options: ['small', 'medium', 'large'],
		},
		newWindow: {
			control: 'boolean',
		},
	},

	parameters: {
		docs: {
			description: {
				component: 'A link component for external destinations with external-link affordances.',
			},
		},
	},
};

const Template: StoryFn = (args, { argTypes }) => ({
	setup: () => ({ args }),
	props: Object.keys(argTypes),
	components: {
		N8nExternalLink,
	},
	template: '<N8nExternalLink v-bind="args">{{ args.default }}</N8nExternalLink>',
});

export const IconOnly = Template.bind({});
IconOnly.args = {
	href: 'http://localhost',
	size: 'medium',
	newWindow: true,
};

export const WithText = Template.bind({});
WithText.args = {
	href: 'http://localhost',
	size: 'medium',
	newWindow: true,
	default: 'Visit n8n',
};

export const Small = Template.bind({});
Small.args = {
	href: 'http://localhost',
	size: 'small',
	newWindow: true,
	default: 'Visit n8n',
};

export const Large = Template.bind({});
Large.args = {
	href: 'http://localhost',
	size: 'large',
	newWindow: true,
	default: 'Visit n8n',
};

export const SameWindow = Template.bind({});
SameWindow.args = {
	href: 'http://localhost',
	size: 'medium',
	newWindow: false,
	default: 'Visit n8n',
};

export const WithClickHandler = Template.bind({});
WithClickHandler.args = {
	size: 'medium',
	onClick: () => alert('Clicked!'),
	default: 'Click me',
};
