# Lahza Studio

Lahza Studio — Mac, Windows va Linux uchun video muharriri. Timeline montaji,
subtitrlar, audio mikser, effektlar, animatsiya va apparat tezlashtirishli eksportni
qo'llaydi. Lokal MCP server orqali AI agentlar ochiq loyihani boshqarishi mumkin.

Lahza engine integratsiyasi o'zbekcha transkripsiya, qiziqarli lahzalarni topish,
9:16 kadr rejalari va karaoke subtitrlarini qo'shadi. Bu imkoniyatlar uchun engine
alohida tayyorlanadi; modellar o'rnatilgandan keyin lokal ishlaydi.

## Mac'da ishga tushirish

Talablar: macOS 13+, Node 24+, Rust va Xcode Command Line Tools.

```sh
npm ci
npm run bootstrap
npm run dev
```

`bootstrap` Electron va FFmpeg'ni tayyorlaydi, Rust native modullarini yig'adi.
`dev` WebAssembly modullarini yig'ib, desktop oynasini ochadi.

Lahza engine tayyor bo'lgan manba papkasidan ulash:

```sh
node apps/desktop/scripts/stage-lahza-engine.mjs --from /absolute/path/to/engine-checkout
```

Batafsil: [muhitni tayyorlash](docs/setup.md), [arxitektura](docs/architecture.md),
[MCP](docs/mcp.md).

## Tekshirish va build

```sh
npm run typecheck
npm test
npm run test:scripts
npm run build
npm run package
```

[Testlar](docs/agents/testing.md) · [Motif yaratish](docs/motif-authoring.md) ·
[Arxitektura qarorlari](docs/adr/)

## Loyiha va litsenziya

[Manba kodi va muammolar](https://github.com/AbduxalilVoxidjonov/lahza.uz).

Asl muharrir kodi: Copyright (c) 2026 UncleChair. MIT litsenziyasi va mualliflik
qaydi [LICENSE](LICENSE) faylida saqlanadi. FFmpeg hamda boshqa komponentlar
litsenziyalari: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
