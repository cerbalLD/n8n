const glob = require('fast-glob');
const fs = require('fs');
const path = require('path');

function copyJsonFiles(baseDir) {
	const files = glob.sync(
		[
			'nodes/**/*.node{,.ee}.json',
			'nodes/**/translations/**/*.json',
			'credentials/translations/**/*.json',
		],
		{ cwd: baseDir },
	);
	for (const file of files) {
		fs.mkdirSync(path.dirname(path.resolve(baseDir, 'dist', file)), { recursive: true });
		fs.copyFileSync(path.resolve(baseDir, file), path.resolve(baseDir, 'dist', file));
	}
}

copyJsonFiles(process.argv[2]);
