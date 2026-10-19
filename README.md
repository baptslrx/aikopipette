# AikoPipette

Une pipette pour prendre une couleur **n'importe où sur l'écran**, avec un historique et la palette principale d'une image. Tout se passe en local.

Le thème s'adapte au système : panneau **noir** en mode sombre, **blanc** en mode clair, avec un accent **bleu clair**, comme AikoRoue.

- **Alt + C** (⌥ C sur Mac) : la loupe apparaît. Clique sur une couleur et elle est copiée (HEX, RGB ou HSL au choix), puis ajoutée à l'historique. **Échap** annule. Sous Windows et Linux, les **flèches** déplacent la souris au pixel près.
- **Clic sur l'icône pipette** (barre des menus sur Mac, près de l'horloge sous Windows et Linux) : l'historique (clic sur une pastille pour la recopier, clic droit pour un autre format ou pour la supprimer), le format de copie, et une zone où **glisser une image pour obtenir sa palette**.
- **Le raccourci se change** dans le panneau, via **⋯ → Changer le raccourci…**.

## Téléchargements

Chaque envoi sur `main` compile les trois versions (onglet **Actions**). Pour publier : **Actions → Publier une version**, avec le numéro de la compilation et la version (ex. `v1.0.1`).

| Système | Fichier | Installation |
|---|---|---|
| Windows 10/11 | `AikoPipette-Windows-Setup.exe` | Double-clic. Si Windows affiche « Windows a protégé votre ordinateur » : **Informations complémentaires → Exécuter quand même**. |
| Mac (macOS 13+) | `AikoPipette-Mac.zip` | Dézipper, glisser dans Applications. Au premier lancement : **Réglages Système → Confidentialité et sécurité → Ouvrir quand même**. |
| Linux x86_64 | `AikoPipette-Linux-x86_64.tar.gz` | Extraire, puis lancer `./installer.sh`. |

**Linux sous Wayland** (Ubuntu ou Fedora récents) : ces bureaux interdisent aux applis de capturer l'écran et d'avoir un raccourci global. La pipette n'y est donc pas disponible, mais la palette d'une image fonctionne. Sous X11, tout fonctionne.

## Organisation du code

```
macos/      Appli Mac native (Swift, SwiftUI) — loupe système de macOS, raccourci global Carbon
desktop/    Appli Windows/Linux (Python, Qt) — python -m aikopipette
packaging/  Installateur Windows et script Linux
assets/     Icônes
```
