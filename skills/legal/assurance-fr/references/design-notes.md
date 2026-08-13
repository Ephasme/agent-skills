# Notes de conception du prompt

Pourquoi `SKILL.md` est écrit ainsi. Chaque choix renvoie à une source éditeur ouverte le
**2026-08-13**. Ce fichier n'est pas destiné à l'utilisateur final : il sert à qui voudra
modifier le prompt sans défaire ce qui a été choisi délibérément.

## Contents

- [Sources](#sources)
- [Décisions et leur justification](#décisions-et-leur-justification)
- [Utilisation hors compétence](#utilisation-hors-compétence)

## Sources

- Anthropic, *Prompting best practices*, référence vivante pour la génération Claude
  actuelle : [platform.claude.com](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- Anthropic, *The new rules of context engineering for Claude 5 generation models*,
  **24 juillet 2026** : [claude.com/blog](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)
- Anthropic, *Prompt engineering best practices*, 10 novembre 2025 :
  [claude.com/blog](https://claude.com/blog/best-practices-for-prompt-engineering)
- Anthropic, *Effective context engineering for AI agents*, 29 septembre 2025 :
  [anthropic.com/engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic, *Reduce hallucinations* :
  [platform.claude.com](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- OpenAI, *Model Spec*, version du **18 décembre 2025** : [model-spec.openai.com](https://model-spec.openai.com)

## Décisions et leur justification

### Un rôle court et plat, pas un superlatif
La demande initiale était de « primer avec la plus forte séniorité ». La forme
maximaliste est contre-indiquée par la source la plus directe sur ce point : « Don't
over-constrain the role. 'You are a helpful assistant' is often better than 'You are a
world-renowned expert who only speaks in technical jargon and never makes mistakes.'
Overly specific roles can limit the AI's helpfulness » (Anthropic, blog du 10 novembre
2025, section *Role prompting*). La séniorité est donc encodée **par le standard de
travail** — qualifier avant de conclure, remonter au texte en vigueur, distinguer l'acquis
du discuté — et non par un adjectif. La page de référence maintient par ailleurs qu'un
rôle bref reste utile : « Setting a role in the system prompt focuses Claude's behavior
and tone for your use case. Even a single sentence makes a difference. »

### Peu de règles absolues, beaucoup de jugement
« Then: Give Claude rules → Now: Let Claude use judgement ». Anthropic rapporte avoir
supprimé plus de 80 % du prompt système de son agent de codage sans perte mesurable, les
instructions rigides entrant en conflit avec les demandes réelles des utilisateurs (post
du 24 juillet 2026). D'où six règles non négociables seulement — celles où l'erreur est
irréversible : citation vérifiée, version en vigueur, hiérarchie des sources, échelle de
nuance, droit de dire « je ne sais pas », marquage de l'inférence. Le reste est formulé
comme principe.

### Divulgation progressive plutôt que tout en tête
« Then: Put it all upfront → Now: Use progressive disclosure », et pour les compétences :
« For long skills, try and use progressive disclosure as much as possible — divide it into
many files and split them out » (même post). D'où un `SKILL.md` court portant les acquis
qui doivent être en mémoire de travail, et sept fichiers de référence chargés à la
demande. La consigne « It's best when skills encode particular opinions, knowledge, or
best practices » justifie les rubriques **Piège** : ce que le texte ne dit pas et qu'un
junior manque.

### Formulation positive
« Tell Claude what to do instead of what not to do » (page de référence, *Control the
format of responses*). Les consignes sont donc rédigées à l'affirmative — « un article
cité est un article lu » plutôt que « n'invente pas de références ».

### Pas de majuscules d'alarme
« Where you might have said 'CRITICAL: You MUST use this tool when…', you can use more
normal prompting like 'Use this tool when…' » — les modèles récents sur-déclenchent sur
le langage impératif (même page, section *Tool usage*). Le prompt n'en contient aucune.

### Permission explicite d'ignorer, et échelle de nuance
« Allow Claude to say "I don't know": Explicitly give Claude permission to admit
uncertainty. This simple technique can drastically reduce false information » (Anthropic,
*Reduce hallucinations*). L'échelle retenue est celle, plus granulaire, du Model Spec
d'OpenAI : « confident right answer > hedged right answer > no answer > hedged wrong
answer > confident wrong answer », assortie de la règle d'escalade : « High-stakes or
risky situations, where inaccuracies may lead to significant real-world consequences,
require heightened caution and more explicit expressions of uncertainty ». Les deux
éditeurs convergent ; c'est la formulation la plus opérationnelle qui a été reprise.

### Réponse substantielle + réserve + orientation, jamais le refus sec
C'est la source la plus directement applicable à un agent de conseil juridique. Model
Spec, section *Provide information without giving regulated advice* : « For advice on
sensitive or important topics (e.g., legal, medical, and financial matters), the assistant
should equip the user with information without providing definitive advice that would be
best given by a licensed professional. A concise disclaimer should also be included
stating that the assistant is not a professional in that domain and/or recommending that
the user seek qualified, licensed help when appropriate. » Le Model Spec classe
explicitement comme **violation** le refus poli sans contenu utile. D'où la formulation
retenue dans `SKILL.md`, qui interdit le refus sec.

### Ancrage dans les citations
« Ground responses in quotes: For long document tasks, ask Claude to quote relevant parts
of the documents first before carrying out its task » (page de référence, *Long context
prompting*), et « Use direct quotes for factual grounding » (*Reduce hallucinations*).
D'où des fichiers de référence bâtis sur des citations verbatim datées plutôt que sur des
reformulations : le modèle cite la source, il ne la paraphrase pas.

### Peu d'exemples, un seul, orienté format
Un exemple unique, balisé, montrant la **forme** attendue. Deux raisons convergentes : la
page de référence recommande 3 à 5 exemples pour steer *le format*, mais le post du
24 juillet 2026 avertit que « giving examples actually constrains them to a certain
exploration space » pour le *comportement*. Un raisonnement juridique ne doit pas être
contraint par un gabarit d'espèce ; la mise en forme, si.

### Titres Markdown, balises XML réservées
Le blog du 10 novembre 2025 rétrograde les balises XML : « modern models are better at
understanding structure without XML tags… clear headings, whitespace, and explicit
language work just as well with less overhead ». Le post du 29 septembre 2025 traite les
deux comme interchangeables. D'où des titres Markdown pour la structure, et une balise
`<exemple>` uniquement là où une frontière de contenu doit être non ambiguë.

### Ce qui a été délibérément écarté
- **Le bloc `<persistence>`** d'OpenAI (« never stop or hand back to the user when you
  encounter uncertainty ») : incompatible avec un domaine où l'aveu d'incertitude est la
  bonne conduite.
- **Les consignes d'auto-vérification systématique** : la page de référence indique, pour
  les modèles du palier le plus capable, qu'ils vérifient leur travail sans qu'on le leur
  demande et que des consignes de vérification héritées de prompts plus anciens
  provoquent une sur-vérification (section *Thinking*).
- **Le prefill** : non supporté à partir de Claude 4.6 (« Requests with prefilled
  assistant messages to these models return a 400 error »).

## Utilisation hors compétence

Le corps de `SKILL.md`, sans son en-tête YAML, fonctionne tel quel comme prompt système.
Dans ce cas, deux adaptations :

1. Remplacer les liens relatifs `references/*.md` par le contenu réellement fourni au
   modèle, ou par la procédure d'accès à ces fichiers.
2. Si le contexte le permet, placer le contenu de référence **avant** les instructions :
   « Put longform data at the top: Place your long documents and inputs near the top of
   your prompt, above your query, instructions, and examples. This improves performance
   across all models » (page de référence, *Long context prompting*). C'est le seul point
   de divergence relevé entre les deux éditeurs — la documentation OpenAI place le
   contexte en fin de message développeur, mais pour des données variables par requête,
   non pour un corpus de référence stable.
