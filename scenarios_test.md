# Scénarios de Test MEDIBOT — Démonstration Profs

> **Commande** : `python run.py --pepper`
> 
> **Avant chaque scénario** : Redémarrer Rasa (`Ctrl+C` → relancer) pour repartir propre.
> **Dashboard** : Ouvrir `http://localhost:5173` dans le navigateur pour montrer les alertes en temps réel.

---

## Scénario 1 — Flow complet "tout va bien" 🟢
**Durée** : ~2 min | **Prouve** : identification, LEDs, chanson, fin propre

| Étape | Tu dis | Le robot fait | Ce qu'il faut filmer |
|-------|--------|---------------|---------------------|
| 1 | *(rien)* | "Bonsoir, c'est Pepper, quel est votre nom ?" | Le robot parle en premier |
| 2 | "Je suis Ouassim" | "Parfait ! Je vous ai identifié, Ouassim Arioui. Ça va bien ?" | Identification réussie |
| 3 | **Sourire devant la caméra** | LEDs → **VERT** 🟢 | Les LEDs réagissent aux émotions |
| 4 | "Oui ça va" | "Chanson ou discuter ?" | Pas d'urgence déclenchée |
| 5 | "Une chanson" | 🎵 Joue une mélodie + LEDs musicales | Musique instrumentale |
| 6 | *(fin)* | "Bonne nuit !" | Conversation terminée proprement |

---

## Scénario 2 — Flow complet "ça ne va pas" → urgence confirmée 🔴
**Durée** : ~2 min | **Prouve** : détection mal-être, alerte, suspension dialogue

| Étape | Tu dis | Le robot fait | Ce qu'il faut filmer |
|-------|--------|---------------|---------------------|
| 1 | *(rien)* | "Bonsoir... quel est votre nom ?" | |
| 2 | "Je suis Ouassim" | "Parfait ! Ça va bien ?" | |
| 3 | "Non ça ne va pas" | "Souhaitez-vous que j'appelle l'équipe d'urgence ?" | Le robot propose de l'aide |
| 4 | **Faire un visage triste** | LEDs → **ORANGE** 🟠 | LEDs réagissent à la tristesse |
| 5 | "Oui" | "Je vais chercher quelqu'un. Restez calme." | Alerte envoyée |
| 6 | | | **Montrer le dashboard** : alerte visible |

---

## Scénario 3 — Flow "ça ne va pas" → refuse aide → blague 🟡
**Durée** : ~2 min | **Prouve** : confort alternatif, vision activée en arrière-plan

| Étape | Tu dis | Le robot fait |
|-------|--------|---------------|
| 1-2 | *(identification)* | *(comme avant)* |
| 3 | "Non ça ne va pas" | "Souhaitez-vous que j'appelle l'urgence ?" |
| 4 | "Non" | "Une blague ou une musique apaisante ?" |
| 5 | "Une blague" | Raconte une blague + "Bonne nuit !" |

---

## Scénario 4 — Détection d'émotions en temps réel 🎭
**Durée** : ~3 min | **Prouve** : toutes les couleurs de LEDs

> Faire ce scénario APRÈS l'identification (scénario 1 étapes 1-3).

| Expression faciale | LEDs attendues | Couleur |
|-------------------|----------------|---------|
| 😊 Sourire franc | Vert clignotant | 🟢 |
| 😐 Visage neutre | Blanc standard | ⚪ |
| 😢 Visage triste | Orange doux | 🟠 |
| 😡 Visage en colère | Rouge fixe | 🔴 |
| 😲 Visage surpris | Orange bref | 🟠 |

> **Astuce** : Rester 3-4 secondes sur chaque expression (stabilisation 3 frames).

---

## Scénario 5 — Questions du patient 💬
**Durée** : ~2 min | **Prouve** : les fonctionnalités de dialogue (heure, date, médicaments, sortie)

> Après identification + "oui ça va" + "je veux discuter" :

| Tu dis | Le robot répond |
|--------|----------------|
| "Quelle heure est-il ?" | "Il est actuellement 22:15." |
| "On est quel jour ?" | "Nous sommes le 23/04/2026." |
| "C'est quand mon médicament ?" | Affiche le traitement depuis la DB |
| "Je sors quand ?" | "Votre date de sortie est le ..." |
| "Appelle une infirmière" | "J'ai prévenu l'infirmière." + alerte dashboard |

---

## Scénario 6 — Silence du patient ⏱️
**Durée** : ~1 min | **Prouve** : gestion du timeout de silence

| Étape | Action | Le robot fait |
|-------|--------|---------------|
| 1-3 | *(identification + "ça ne va pas")* | "Voulez-vous que j'appelle l'urgence ?" |
| 4 | **Ne rien dire pendant 5 secondes** | "Je ne vous entends pas. Je préviens l'équipe médicale." |
| 5 | | **Dashboard** : alerte de silence visible |

---

## Scénario 7 — Urgence vocale directe 🚨
**Durée** : ~30s | **Prouve** : intent d'urgence prioritaire

| Étape | Tu dis | Le robot fait |
|-------|--------|---------------|
| 1 | *(après identification)* | |
| 2 | "SOS j'ai besoin d'aide !" | Alerte immédiate + "Une infirmière va arriver." |
| 3 | | **Dashboard** : alerte urgence critique |

---

## Scénario 8 — Dashboard en temps réel 📊
**Durée** : ~1 min | **Prouve** : monitoring complet

> Ouvrir `http://localhost:5173` et montrer :

- [ ] Liste des alertes avec horodatage
- [ ] Sévérité (couleur) : low / medium / high / critical
- [ ] Nom du patient et numéro de chambre
- [ ] Nouvelles alertes qui apparaissent en temps réel (refaire le scénario 2 avec le dashboard ouvert)

---

## Checklist de ce qu'il faut montrer aux profs

- [ ] **Le robot parle en premier** (scénario 1, étape 1)
- [ ] **Identification par prénom** depuis la base de données (scénario 1, étape 2)
- [ ] **LEDs réactives aux émotions** — sourire→vert, triste→orange (scénario 4)
- [ ] **Pas de faux EMERGENCY** quand le patient dit "ça va" (scénario 1)
- [ ] **Proposition d'aide** quand le patient va mal (scénario 2)
- [ ] **Alerte urgence** avec notification dashboard (scénario 2, étape 6)
- [ ] **Confort alternatif** : blague ou musique (scénario 3)
- [ ] **Chanson instrumentale** avec mélodie WAV (scénario 1, étape 5)
- [ ] **Questions patient** : heure, date, médicaments, sortie (scénario 5)
- [ ] **Silence détecté** : relance puis alerte (scénario 6)
- [ ] **Urgence vocale directe** : "SOS" (scénario 7)
- [ ] **Dashboard temps réel** avec alertes (scénario 8)
- [ ] **Le dialogue se coupe** pendant une urgence vision (si testable)
