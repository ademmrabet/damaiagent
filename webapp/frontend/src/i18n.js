// Static UI-chrome translations for the Chat page (2026-09-03, see
// docs/decisions.md). Deliberately separate from the LLM-based
// translation shim in llm/translate.py (Python) - that path exists
// for arbitrary, dynamic DAM answer text where the exact wording
// can't be known ahead of time. This file is the opposite case: a
// small, fixed set of interface strings (button labels, placeholders,
// meta text) that are the same on every load - translating those with
// an LLM call would be slower, cost money on every page view, and
// risk a slightly different phrasing each time for text that should
// be stable. Hand-translated once, here, like any normal i18n
// dictionary.
//
// Scope: the Chat page only (header subtitle, input area, message
// meta line, empty state). The conversation sidebar ("+ New chat",
// timestamps) and the Dashboard page are left in English for now -
// a reasonable follow-up, not folded into this pass.

export const LANGUAGE_NAMES = {
  fr: 'French',
  es: 'Spanish',
  pt: 'Portuguese',
  ar: 'Arabic',
};

// Options shown in the LanguagePicker - kept separate from
// LANGUAGE_NAMES (used for the small per-message badge, always in
// English) since these are the picker's own display labels, correctly
// self-named in each language rather than translated from English.
export const LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto', sub: 'detect from question' },
  { value: 'en', label: 'English', sub: '' },
  { value: 'fr', label: 'Français', sub: '' },
  { value: 'es', label: 'Español', sub: '' },
  { value: 'pt', label: 'Português', sub: '' },
  { value: 'ar', label: 'العربية', sub: '' },
];

export const RTL_LANGUAGES = new Set(['ar']);

export const UI_STRINGS = {
  en: {
    subtitle:
      'Delegation of Authority Matrix · ask who approves, reviews, checks, initiates, or must be informed for any activity',
    dashboardLink: 'Dashboard →',
    emptyState:
      'Try: “who approves 2.126?” or “who needs to be informed for quarterly mission program”',
    placeholder: 'Ask about the DAM...',
    send: 'Send',
    matchedById: 'matched by id',
    matchedByText: 'matched by text search',
    carriedOver: 'carried over from previous question',
    confidence: 'confidence',
    lowConfidence: 'low confidence',
    phrasedBy: 'phrased by',
    llmUnavailable: 'LLM unavailable, showed template answer',
    answeredIn: 'answered in',
    translationFailed: "couldn't translate, showed the English answer",
    showDeterministic: 'Show structured (template) answer',
    hideDeterministic: 'Hide structured (template) answer',
    connectionError: 'Something went wrong reaching the agent. Is the server running?',
  },
  fr: {
    subtitle:
      "Matrice de délégation d'autorité (DAM) · demandez qui approuve, examine, vérifie, initie ou doit être informé pour toute activité",
    dashboardLink: 'Tableau de bord →',
    emptyState:
      'Essayez : « qui approuve 2.126 ? » ou « qui doit être informé pour le programme de mission trimestriel »',
    placeholder: 'Posez une question sur le DAM...',
    send: 'Envoyer',
    matchedById: 'trouvé par identifiant',
    matchedByText: 'trouvé par recherche textuelle',
    carriedOver: 'repris de la question précédente',
    confidence: 'confiance',
    lowConfidence: 'confiance faible',
    phrasedBy: 'formulé par',
    llmUnavailable: 'LLM indisponible, réponse type affichée',
    answeredIn: 'réponse en',
    translationFailed: "traduction impossible, réponse affichée en anglais",
    showDeterministic: 'Afficher la réponse structurée (modèle)',
    hideDeterministic: 'Masquer la réponse structurée (modèle)',
    connectionError: "Un problème est survenu en contactant l'agent. Le serveur est-il actif ?",
  },
  es: {
    subtitle:
      'Matriz de Delegación de Autoridad (DAM) · pregunte quién aprueba, revisa, verifica, inicia o debe ser informado de cualquier actividad',
    dashboardLink: 'Panel →',
    emptyState:
      'Pruebe: «¿quién aprueba 2.126?» o «quién debe ser informado del programa de misión trimestral»',
    placeholder: 'Pregunte sobre el DAM...',
    send: 'Enviar',
    matchedById: 'encontrado por id',
    matchedByText: 'encontrado por búsqueda de texto',
    carriedOver: 'continuado de la pregunta anterior',
    confidence: 'confianza',
    lowConfidence: 'confianza baja',
    phrasedBy: 'redactado por',
    llmUnavailable: 'LLM no disponible, se mostró la respuesta plantilla',
    answeredIn: 'respondido en',
    translationFailed: 'no se pudo traducir, se mostró la respuesta en inglés',
    showDeterministic: 'Mostrar respuesta estructurada (plantilla)',
    hideDeterministic: 'Ocultar respuesta estructurada (plantilla)',
    connectionError: 'Algo salió mal al contactar al agente. ¿Está el servidor en ejecución?',
  },
  pt: {
    subtitle:
      'Matriz de Delegação de Autoridade (DAM) · pergunte quem aprova, revisa, verifica, inicia ou deve ser informado sobre qualquer atividade',
    dashboardLink: 'Painel →',
    emptyState:
      'Experimente: «quem aprova 2.126?» ou «quem deve ser informado sobre o programa de missão trimestral»',
    placeholder: 'Pergunte sobre o DAM...',
    send: 'Enviar',
    matchedById: 'encontrado por id',
    matchedByText: 'encontrado por busca de texto',
    carriedOver: 'herdado da pergunta anterior',
    confidence: 'confiança',
    lowConfidence: 'confiança baixa',
    phrasedBy: 'formulado por',
    llmUnavailable: 'LLM indisponível, resposta padrão exibida',
    answeredIn: 'respondido em',
    translationFailed: 'não foi possível traduzir, resposta exibida em inglês',
    showDeterministic: 'Mostrar resposta estruturada (modelo)',
    hideDeterministic: 'Ocultar resposta estruturada (modelo)',
    connectionError: 'Algo deu errado ao contatar o agente. O servidor está em execução?',
  },
  ar: {
    subtitle:
      'مصفوفة تفويض الصلاحيات (DAM) · اسأل من يوافق، يراجع، يتحقق، يبادر، أو يجب إبلاغه بأي نشاط',
    dashboardLink: 'لوحة التحكم ←',
    emptyState:
      'جرّب: «من يوافق على 2.126؟» أو «من يجب إبلاغه ببرنامج المهمة الفصلي»',
    placeholder: 'اسأل عن DAM...',
    send: 'إرسال',
    matchedById: 'تمت المطابقة بالمعرف',
    matchedByText: 'تمت المطابقة بالبحث النصي',
    carriedOver: 'منقول من السؤال السابق',
    confidence: 'الثقة',
    lowConfidence: 'ثقة منخفضة',
    phrasedBy: 'تمت الصياغة بواسطة',
    llmUnavailable: 'النموذج غير متاح، تم عرض الإجابة الجاهزة',
    answeredIn: 'تمت الإجابة باللغة',
    translationFailed: 'تعذّرت الترجمة، عُرضت الإجابة بالإنجليزية',
    showDeterministic: 'إظهار الإجابة النموذجية',
    hideDeterministic: 'إخفاء الإجابة النموذجية',
    connectionError: 'حدث خطأ أثناء الاتصال بالوكيل. هل الخادم يعمل؟',
  },
};

// uiLanguage is 'auto'/'en'/'fr'/'es'/'pt'/'ar' - the picker's own
// value. 'auto' has no dedicated dictionary (there's nothing to
// "detect" for static UI chrome - only actual DAM answers get
// detected per-question) so it falls back to English chrome, same as
// picking English explicitly.
export function stringsFor(uiLanguage) {
  return UI_STRINGS[uiLanguage] || UI_STRINGS.en;
}
