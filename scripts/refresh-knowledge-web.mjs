#!/usr/bin/env node
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative } from "node:path";

const repoRoot = process.cwd();
const projectsJsonPath = join(repoRoot, "projects", "projects.json");
const knowledgeDir = join(repoRoot, "knowledge");
const projectsIndexPath = join(knowledgeDir, "projects-index.md");
const linkMapPath = join(knowledgeDir, "link-map.md");

function readProjects() {
  const raw = readFileSync(projectsJsonPath, "utf8");
  return JSON.parse(raw);
}

function collectReadmes(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (entry === ".git" || entry === "node_modules" || entry === "dist" || entry === ".astro") continue;
      collectReadmes(full, out);
    } else if (entry.toLowerCase() === "readme.md") {
      out.push(relative(repoRoot, full).replaceAll("\\", "/"));
    }
  }
  return out.sort();
}

function renderProjectsIndex(data) {
  const lines = [
    "# Projects Index",
    "",
    "Auto-generated from `projects/projects.json`.",
    "",
    "## Primary",
    "",
  ];

  for (const item of data.en.filter((p) => p.tier === "primary")) {
    const target = item.repoUrl ? item.repoUrl : "";
    lines.push(`- **${item.title}**${target ? ` - [open](${target})` : ""}`);
  }

  lines.push("", "## Secondary", "");

  for (const item of data.en.filter((p) => p.tier === "secondary")) {
    const target = item.repoUrl ? item.repoUrl : "";
    lines.push(`- **${item.title}**${target ? ` - [open](${target})` : ""}`);
  }

  lines.push("", "## Related", "", "- [Home](../README.md)", "- [Projects](../projects/README.md)", "- [Knowledge](README.md)");
  return `${lines.join("\n")}\n`;
}

function renderLinkMap(readmes) {
  const lines = [
    "# Link Map",
    "",
    "Auto-generated map of core readable entry points.",
    "",
    "## README pages",
    "",
  ];

  for (const file of readmes) {
    lines.push(`- [\`${file}\`](../${file})`);
  }

  lines.push(
    "",
    "## Core entry points",
    "",
    "- [Home](../README.md)",
    "- [Projects](../projects/README.md)",
    "- [Knowledge](README.md)",
    "- [Automation](../automation/README.md)",
    "- [Portfolio site source](../web/README.md)"
  );

  return `${lines.join("\n")}\n`;
}

if (!existsSync(projectsJsonPath)) {
  console.error(`missing ${projectsJsonPath}`);
  process.exit(1);
}

const projects = readProjects();
const readmes = collectReadmes(repoRoot).filter((p) => !p.startsWith("projects/repos/"));

writeFileSync(projectsIndexPath, renderProjectsIndex(projects), "utf8");
writeFileSync(linkMapPath, renderLinkMap(readmes), "utf8");
console.log("refresh-knowledge-web: updated knowledge/projects-index.md and knowledge/link-map.md");
