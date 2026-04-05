/**
 * Technical projects — plain narrative, no template labels in the UI.
 * https://github.com/Arzuparreta
 */
import type { Locale } from '../i18n/config';

/** Public URL from site root (served from `public/`). */
const IMG_SOUNDSIBLE_MOBILE = '/images/projects/soundsible-mobile.png';
const IMG_DOCKER_READER_LIGHT = '/images/projects/docker-reader-light.png';

const SYNESTHETIC_DEMO_YOUTUBE =
	'https://www.youtube.com/watch?v=umtcc_3KsfI&list=PL4wUTace1gknGv08vVZ4xtOPwTX8arWlG&index=2';

export type ProjectTier = 'primary' | 'secondary';

export type PrimaryProject = {
	slug: string;
	title: string;
	/** Comma-separated core technologies (shown after title). */
	tech: string;
	/** What it is and what problem it solves. */
	why: string;
	/** One or two concrete technical or operational details. */
	how: [string] | [string, string];
	/** Public repo URL; omit when the entry is not tied to a GitHub project (no title link or repo button). */
	repoUrl?: string;
	/** Optional landing page (e.g. GitHub Pages): title link and card background clicks use this when set. */
	projectSiteUrl?: string;
	tier: 'primary';
	/** Optional screenshot path under site root. */
	imageSrc?: string;
	/** Optional external demo (e.g. video). */
	demoUrl?: string;
};

export type SecondaryProject = {
	slug: string;
	title: string;
	tech: string;
	/** Single sentence for compact listing. */
	summary: string;
	repoUrl: string;
	tier: 'secondary';
};

export type Project = PrimaryProject | SecondaryProject;

const projectsEn: Project[] = [
	{
		slug: 'homelab',
		title: 'Remote administration & homelab',
		tech: 'Debian, Tailscale, Pi-hole, SSH, Mosh',
		why:
			'A headless home server in Seville I use every day for reliable remote access, DNS filtering, and network-wide ad blocking—without exposing SSH to the public internet.',
		how: [
			'I reach it from a ThinkPad over Tailscale with Mosh for resilient sessions; Pi-hole runs on the mesh for whole-network filtering.',
			'Tailscale is the only way in—no open SSH port on the router.',
		],
		tier: 'primary',
	},
	{
		slug: 'soundsible',
		title: 'soundsible',
		tech: 'JavaScript, Node, SQLite, Docker, Python',
		why:
			'Self-hosted music environment aimed at a full streaming-style experience: search and manage your library, play from any device, and keep queues and settings in sync—your files, your infrastructure.',
		how: [
			'Python launcher and browser-based Station on a headless Linux host; SQLite backs the catalog and metadata.',
			'I run it as everyday home infrastructure; remote access works cleanly over Tailscale when I need it off-LAN.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/soundsible',
		projectSiteUrl: 'https://arzuparreta.github.io/soundsible.github.io/',
		imageSrc: IMG_SOUNDSIBLE_MOBILE,
	},
	{
		slug: 'synesthetic-visualizer',
		title: 'synesthetic-visualizer',
		tech: 'Rust, real-time audio, GPU-oriented graphics',
		why:
			'Desktop visualizer that shows harmony and musical form in 3D—consonance and movement read as geometry on a Tonnetz-style spiral, not a plain volume or spectrum bar.',
		how: [
			'Rust handles capture and GPU rendering end to end so the image stays tight to the audio with minimal delay.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/synesthetic-visualizer',
		demoUrl: SYNESTHETIC_DEMO_YOUTUBE,
	},
	{
		slug: 'docker-reader',
		title: 'docker-reader',
		tech: 'Docker, Docker Compose, JavaScript',
		why:
			'PDF library in Docker: upload books, read in the browser, and resume on any device—multi-user so each account keeps its own progress.',
		how: [
			'Docker Compose plus a small config file set users, port, and volumes—the same deploy on every host.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/docker-reader',
		imageSrc: IMG_DOCKER_READER_LIGHT,
	},
	{
		slug: 'brain',
		title: 'brain',
		tech: 'Python',
		summary:
			'Minimal terminal tool to add, edit, and list Markdown notes in one folder—plain Python, no install beyond the interpreter.',
		repoUrl: 'https://github.com/Arzuparreta/brain',
		tier: 'secondary',
	},
	{
		slug: 'remove-multi-titles-yt',
		title: 'remove-multi-titles-yt',
		tech: 'JavaScript, WebExtensions',
		summary:
			'Chrome/Firefox extension that remembers the first title you saw for each video and keeps it when YouTube A/B-tests different titles for the same clip.',
		repoUrl: 'https://github.com/Arzuparreta/remove-multi-titles-yt',
		tier: 'secondary',
	},
];

const projectsEs: Project[] = [
	{
		slug: 'homelab',
		title: 'Administración remota y homelab',
		tech: 'Debian, Tailscale, Pi-hole, SSH, Mosh',
		why:
			'Servidor casero sin monitor en Sevilla que uso a diario: acceso remoto fiable, filtrado DNS y bloqueo de anuncios en toda la red, sin abrir SSH a internet.',
		how: [
			'Acceso desde un ThinkPad por Tailscale y Mosh; Pi-hole en la malla para filtrar a nivel de red.',
			'Solo entro por Tailscale—no hay SSH expuesto al router.',
		],
		tier: 'primary',
	},
	{
		slug: 'soundsible',
		title: 'Soundsible',
		tech: 'JavaScript, Node, SQLite, Docker, Python',
		why:
			'Entorno musical autoalojado pensado como un servicio de streaming completo: buscar y gestionar tu biblioteca, escuchar desde cualquier dispositivo y mantener cola y ajustes sincronizados—tus archivos, tu servidor.',
		how: [
			'Lanzador en Python e interfaz web “Station” en un Linux sin monitor; SQLite guarda catálogo y metadatos.',
			'Lo uso como infraestructura diaria en casa; con Tailscale el acceso remoto fuera de la LAN es directo.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/soundsible',
		projectSiteUrl: 'https://arzuparreta.github.io/soundsible.github.io/',
		imageSrc: IMG_SOUNDSIBLE_MOBILE,
	},
	{
		slug: 'synesthetic-visualizer',
		title: 'Synesthetic-visualizer',
		tech: 'Rust, Audio en tiempo real, Renderizado GPU',
		why:
			'Visualizador de escritorio que muestra armonía y forma musical en 3D: la consonancia y el movimiento se leen como geometría en una espiral tipo Tonnetz, no como una barra de volumen o un espectro genérico.',
		how: [
			'Rust de punta a punta en captura y renderizado GPU para que la imagen vaya al ritmo del audio con poco retraso.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/synesthetic-visualizer',
		demoUrl: SYNESTHETIC_DEMO_YOUTUBE,
	},
	{
		slug: 'docker-reader',
		title: 'Docker-reader',
		tech: 'Docker, Docker Compose, JavaScript',
		why:
			'Biblioteca de PDFs en Docker: subes libros, lees en el navegador y retomas en cualquier dispositivo; varios usuarios, cada uno con su progreso.',
		how: [
			'Docker Compose y un `config.json` pequeño definen usuarios, puerto y volúmenes—el mismo despliegue en cualquier máquina.',
		],
		tier: 'primary',
		repoUrl: 'https://github.com/Arzuparreta/docker-reader',
		imageSrc: IMG_DOCKER_READER_LIGHT,
	},
	{
		slug: 'brain',
		title: 'Brain',
		tech: 'Python',
		summary:
			'Herramienta de terminal mínima en Python para crear, editar y listar notas Markdown en una carpeta—sin dependencias externas.',
		repoUrl: 'https://github.com/Arzuparreta/brain',
		tier: 'secondary',
	},
	{
		slug: 'remove-multi-titles-yt',
		title: 'Remove-multi-titles-yt',
		tech: 'JavaScript, WebExtensions',
		summary:
			'Extensión para Chrome/Firefox que guarda el primer título que ves de cada vídeo y lo mantiene aunque YouTube pruebe variantes distintas en el mismo contenido.',
		repoUrl: 'https://github.com/Arzuparreta/remove-multi-titles-yt',
		tier: 'secondary',
	},
];

const byLocale: Record<Locale, Project[]> = {
	en: projectsEn,
	es: projectsEs,
};

export function getProjects(locale: Locale): Project[] {
	return byLocale[locale];
}

export function getPrimaryProjects(locale: Locale): PrimaryProject[] {
	return getProjects(locale).filter((p): p is PrimaryProject => p.tier === 'primary');
}

export function getSecondaryProjects(locale: Locale): SecondaryProject[] {
	return getProjects(locale).filter((p): p is SecondaryProject => p.tier === 'secondary');
}
