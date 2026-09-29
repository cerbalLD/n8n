#!/usr/bin/env node
/**
 * Extracts a translation skeleton (displayName/description/placeholder/hint/options/...)
 * for every node and credential in n8n-nodes-base, following the exact key schema
 * vue-i18n's `nodeText()`/`credText()` read at runtime (see
 * packages/frontend/@n8n/i18n/src/index.ts and .../src/utils.ts).
 *
 * Requires a fresh `packages/nodes-base` build (`pnpm --filter n8n-nodes-base build:unchecked`):
 * descriptions are read via require() of the compiled dist output rather than parsing the
 * .node.ts sources, since real node files build `properties` with spreads/helpers that only
 * fully resolve after compilation.
 *
 * Usage:
 *   node extract-dynamic-i18n-skeleton.js [--only name1,name2] [--nodes-only] [--credentials-only]
 *
 * Output: packages/cli/scripts/.dynamic-i18n-skeleton.json
 *   { "<path relative to packages/nodes-base>": <skeleton object>, ... }
 */

const fs = require('fs');
const path = require('path');

const NODES_BASE_DIR = path.resolve(__dirname, '../../nodes-base');
const OUT_FILE = path.join(__dirname, '.dynamic-i18n-skeleton.json');

const args = process.argv.slice(2);
const onlyArg = args.find((a) => a.startsWith('--only='));
const onlyIdx = args.indexOf('--only');
const onlyList = onlyArg
	? onlyArg.slice('--only='.length).split(',')
	: onlyIdx !== -1
		? (args[onlyIdx + 1] || '').split(',')
		: null;
const only = onlyList ? onlyList.map((s) => s.trim().toLowerCase()).filter(Boolean) : null;
const nodesOnly = args.includes('--nodes-only');
const credentialsOnly = args.includes('--credentials-only');

// --- Utilities mirroring packages/frontend/@n8n/i18n/src/utils.ts ---
// Copied verbatim (not imported) because that package is a Vue/TS library not meant to be
// require()'d from a plain Node script. Keep in sync if utils.ts changes.

function normalize(p) {
	return p.replace(/\[.*?\]/g, '').replace('parameters.', '');
}

function insertOptionsAndValues(pathSegments) {
	return pathSegments.reduce((acc, cur, i) => {
		acc.push(cur);
		if (i === pathSegments.length - 1) return acc;
		acc.push(i % 2 === 0 ? 'options' : 'values');
		return acc;
	}, []);
}

const isNestedInCollectionLike = (p) => p.split('.').length >= 3;
const isTopLevelCollection = (p, parameter) =>
	p.split('.').length === 2 && parameter.type === 'collection';
const isNestedCollection = (p, parameter) =>
	p.split('.').length > 2 && parameter.type === 'collection';
const isFixedCollection = (p, parameter) =>
	parameter.type === 'fixedCollection' && p !== 'parameters';

/** Mirrors deriveMiddleKey() — used for a parameter's own displayName/description/hint. */
function middleKeyFull(p, parameter) {
	let middleKey = parameter.name;

	if (isTopLevelCollection(p, parameter) || isNestedInCollectionLike(p)) {
		middleKey = insertOptionsAndValues(normalize(p).split('.')).join('.');
	}

	if (isNestedCollection(p, parameter) || isFixedCollection(p, parameter)) {
		middleKey = insertOptionsAndValues([...normalize(p).split('.'), parameter.name]).join('.');
	}

	return middleKey;
}

/**
 * Mirrors the inline logic reused by placeholder()/optionsOptionDisplayName()/
 * optionsOptionDescription()/collectionOptionDisplayName() — simpler than middleKeyFull,
 * never triggers the fixedCollection self-referencing branch.
 */
function middleKeySimple(p, parameterName) {
	if (isNestedInCollectionLike(p)) {
		return insertOptionsAndValues(normalize(p).split('.')).join('.');
	}
	return parameterName;
}

// --- Skeleton builders ---

function set(target, key, value) {
	if (typeof value !== 'string' || !value.trim()) return;
	if (/^=?\{\{.*\}\}$/.test(value.trim())) return; // expression, not literal text
	target[key] = value;
}

function walkProperties(properties, parentPath, nodeView) {
	if (!Array.isArray(properties)) return;

	for (const p of properties) {
		if (!p || typeof p !== 'object' || !p.name || p.type === 'hidden') continue;

		const currentPath = `${parentPath}.${p.name}`;
		const fullMk = middleKeyFull(currentPath, p);
		const simpleMk = middleKeySimple(currentPath, p.name);

		set(nodeView, `${fullMk}.displayName`, p.displayName);
		set(nodeView, `${fullMk}.description`, p.description);
		set(nodeView, `${fullMk}.hint`, p.hint);
		set(nodeView, `${simpleMk}.placeholder`, p.placeholder);

		// deriveMiddleKey()'s fixedCollection branch computes a self-referencing key
		// (e.g. "fields.options.fields") for a top-level fixedCollection's OWN label that,
		// empirically, the running app does not actually read for that label — it reads the
		// plain "fields.displayName" instead. Emit both so the label translates either way.
		if (fullMk !== simpleMk) {
			set(nodeView, `${simpleMk}.displayName`, p.displayName);
			set(nodeView, `${simpleMk}.description`, p.description);
			set(nodeView, `${simpleMk}.hint`, p.hint);
		}

		if ((p.type === 'options' || p.type === 'multiOptions') && Array.isArray(p.options)) {
			for (const opt of p.options) {
				if (!opt || typeof opt !== 'object' || opt.value === undefined) continue; // skip separators
				set(nodeView, `${simpleMk}.options.${opt.value}.displayName`, opt.name);
				set(nodeView, `${simpleMk}.options.${opt.value}.description`, opt.description);
			}
		}

		if (p.type === 'collection' && Array.isArray(p.options)) {
			set(
				nodeView,
				`${p.name}.multipleValueButtonText`,
				p.typeOptions && p.typeOptions.multipleValueButtonText,
			);
			walkProperties(p.options, currentPath, nodeView);
		}

		if (p.type === 'fixedCollection' && Array.isArray(p.options)) {
			set(
				nodeView,
				`${p.name}.multipleValueButtonText`,
				p.typeOptions && p.typeOptions.multipleValueButtonText,
			);
			set(
				nodeView,
				`${p.name}.addOptionalFieldButtonText`,
				p.typeOptions && p.typeOptions.addOptionalFieldButtonText,
			);
			for (const opt of p.options) {
				if (!opt || !opt.name) continue;
				set(nodeView, `${simpleMk}.options.${opt.name}.displayName`, opt.displayName);
				if (Array.isArray(opt.values)) {
					walkProperties(opt.values, `${currentPath}.${opt.name}`, nodeView);
				}
			}
		}
	}
}

function buildNodeSkeleton(description) {
	const header = {};
	set(header, 'displayName', description.displayName);
	set(header, 'description', description.description);

	const nodeView = {};
	walkProperties(description.properties, 'parameters', nodeView);
	set(nodeView, 'eventTriggerDescription', description.eventTriggerDescription);
	set(nodeView, 'activationMessage', description.activationMessage);

	const skeleton = {};
	if (Object.keys(header).length) skeleton.header = unflatten(header);
	if (Object.keys(nodeView).length) skeleton.nodeView = unflatten(nodeView);
	return skeleton;
}

function buildCredentialSkeleton(description) {
	const out = {};
	for (const p of description.properties || []) {
		if (!p || !p.name) continue;
		if (p.name === 'clientId' || p.name === 'clientSecret') continue; // covered by _reusableDynamicText

		set(out, `${p.name}.displayName`, p.displayName);
		set(out, `${p.name}.description`, p.description);
		set(out, `${p.name}.hint`, p.hint);
		set(out, `${p.name}.placeholder`, p.placeholder);

		if ((p.type === 'options' || p.type === 'multiOptions') && Array.isArray(p.options)) {
			for (const opt of p.options) {
				if (!opt || typeof opt !== 'object' || opt.value === undefined) continue;
				set(out, `${p.name}.options.${opt.value}.displayName`, opt.name);
				set(out, `${p.name}.options.${opt.value}.description`, opt.description);
			}
		}
	}
	return unflatten(out);
}

/** Turns { 'a.b.c': 'x' } into { a: { b: { c: 'x' } } } — dots inside a key are always separators here. */
function unflatten(flat) {
	const root = {};
	for (const [key, value] of Object.entries(flat)) {
		const segments = key.split('.');
		let node = root;
		for (let i = 0; i < segments.length - 1; i++) {
			node = node[segments[i]] ??= {};
		}
		node[segments[segments.length - 1]] = value;
	}
	return root;
}

// --- Version-dir resolution, mirrors packages/cli/src/node-types.ts ---

function isVersionedDirname(dirent) {
	if (!dirent.isDirectory()) return false;
	const ALLOWED_LENGTH = [2, 3]; // v1, v10
	return ALLOWED_LENGTH.includes(dirent.name.length) && dirent.name.toLowerCase().startsWith('v');
}

function getMaxVersionDirname(dir) {
	let entries;
	try {
		entries = fs.readdirSync(dir, { withFileTypes: true });
	} catch {
		return null;
	}
	const dirnames = entries.filter(isVersionedDirname).map((d) => d.name);
	if (!dirnames.length) return null;
	// Mirrors node-types.ts's getMaxVersion: only the dirname's 2nd character is parsed.
	const maxDigit = Math.max(...dirnames.map((d) => parseInt(d.charAt(1), 10)));
	return dirnames.find((d) => parseInt(d.charAt(1), 10) === maxDigit) || `v${maxDigit}`;
}

// --- Node/credential enumeration ---

function loadDescription(distRelPath) {
	const distAbsPath = path.join(NODES_BASE_DIR, distRelPath);
	// eslint-disable-next-line @typescript-eslint/no-var-requires
	const mod = require(distAbsPath);
	const Cls = Object.values(mod).find((v) => typeof v === 'function');
	if (!Cls) return null;
	const inst = new Cls();

	if (inst.nodeVersions) {
		const versions = Object.keys(inst.nodeVersions).map(Number);
		const maxVersion = Math.max(...versions);
		return inst.nodeVersions[maxVersion].description;
	}
	return inst.description;
}

function distNodeToSrcDir(distRelPath) {
	// "dist/nodes/Set/Set.node.js" -> "<abs>/nodes/Set" (also handles the
	// enterprise-edition ".node.ee.js" suffix, e.g. "Evaluation.node.ee.js")
	const rel = distRelPath.replace(/^dist[\\/]/, '').replace(/[\\/][^\\/]+\.node(\.ee)?\.js$/, '');
	return path.join(NODES_BASE_DIR, rel);
}

function collectNodeEntries(pkg) {
	return pkg.n8n.nodes
		.filter((distRelPath) => !only || only.some((f) => distRelPath.toLowerCase().includes(f)))
		.flatMap((distRelPath) => {
			let description;
			try {
				description = loadDescription(distRelPath);
			} catch (err) {
				console.warn(`[node] failed to load ${distRelPath}: ${err.message}`);
				return [];
			}
			if (!description || !description.name) return [];

			const srcDir = distNodeToSrcDir(distRelPath);
			const versionDir = getMaxVersionDirname(srcDir);
			const outDir = versionDir ? path.join(srcDir, versionDir) : srcDir;
			const outPath = path.join(outDir, 'translations', 'ru', `${description.name}.json`);
			const skeleton = buildNodeSkeleton(description);
			if (!Object.keys(skeleton).length) return [];

			const entries = [{ outPath: path.relative(NODES_BASE_DIR, outPath), skeleton }];

			// packages/core/bin/generate-translations (headers.js, used by the nodes panel/search)
			// looks up translations at the FLAT node dir, ignoring version subdirectories — unlike
			// the runtime NDV loader (packages/cli/src/node-types.ts), which does respect them. For
			// versioned nodes, also drop a header-only copy at the flat path so the panel picks it up.
			if (versionDir && skeleton.header) {
				const flatOutPath = path.join(srcDir, 'translations', 'ru', `${description.name}.json`);
				entries.push({
					outPath: path.relative(NODES_BASE_DIR, flatOutPath),
					skeleton: { header: skeleton.header },
				});
			}

			return entries;
		});
}

function collectCredentialEntries(pkg) {
	return pkg.n8n.credentials
		.filter((distRelPath) => !only || only.some((f) => distRelPath.toLowerCase().includes(f)))
		.map((distRelPath) => {
			let description;
			try {
				const distAbsPath = path.join(NODES_BASE_DIR, distRelPath);
				const mod = require(distAbsPath);
				const Cls = Object.values(mod).find((v) => typeof v === 'function');
				description = Cls ? new Cls() : null;
			} catch (err) {
				console.warn(`[credential] failed to load ${distRelPath}: ${err.message}`);
				return null;
			}
			if (!description || !description.name) return null;

			const skeleton = buildCredentialSkeleton(description);
			if (!Object.keys(skeleton).length) return null;

			const outPath = path.join('credentials', 'translations', 'ru', `${description.name}.json`);
			return { outPath, skeleton };
		})
		.filter(Boolean);
}

function main() {
	const pkg = require(path.join(NODES_BASE_DIR, 'package.json'));

	const entries = [
		...(credentialsOnly ? [] : collectNodeEntries(pkg)),
		...(nodesOnly ? [] : collectCredentialEntries(pkg)),
	];

	const aggregate = {};
	for (const { outPath, skeleton } of entries) {
		aggregate[outPath.split(path.sep).join('/')] = skeleton;
	}

	fs.writeFileSync(OUT_FILE, JSON.stringify(aggregate, null, '\t'), 'utf8');
	console.log(`Wrote ${Object.keys(aggregate).length} skeleton entries to ${OUT_FILE}`);
}

main();
