export default {
	extends: ['@commitlint/config-conventional'],
	ignores: [
		// ignore commits from dependabot
		(commit) =>
			(commit.startsWith('chore(deps)') || commit.startsWith('chore(deps-dev)')) && commit.includes('dependabot')
	]
};
