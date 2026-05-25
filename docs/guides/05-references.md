# 05 — References & further reading

A curated, verified bibliography behind the [guides](README.md). Every arXiv ID
and link below was checked. Entries are grouped by topic; the guides cite them by
the short anchor in brackets, e.g. `[ReAct]`.

> These are the foundational, widely-cited works. They're a solid reading path
> from "how do LLMs work" up to "how do agents reason, act, and stay safe."

## Foundations (how the models work)

<a id="transformer"></a>**[Transformer]** Vaswani, A., et al. (2017).
*Attention Is All You Need.* arXiv:1706.03762.
https://arxiv.org/abs/1706.03762
— The architecture underneath modern LLMs.

<a id="instructgpt"></a>**[InstructGPT]** Ouyang, L., et al. (2022).
*Training Language Models to Follow Instructions with Human Feedback.*
arXiv:2203.02155. https://arxiv.org/abs/2203.02155
— Why instruction-following models (and RLHF / human-in-the-loop alignment) work.

## Agents: reasoning and acting

<a id="react"></a>**[ReAct]** Yao, S., et al. (2022).
*ReAct: Synergizing Reasoning and Acting in Language Models.* arXiv:2210.03629.
https://arxiv.org/abs/2210.03629
— The canonical "reason, then act with a tool, then observe" agent loop.

<a id="cot"></a>**[CoT]** Wei, J., et al. (2022).
*Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.*
arXiv:2201.11903. https://arxiv.org/abs/2201.11903
— Prompting a model to "think step by step" before answering.

<a id="reflexion"></a>**[Reflexion]** Shinn, N., et al. (2023).
*Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366.
https://arxiv.org/abs/2303.11366
— Agents that improve by reflecting on their own failures (learning from edits/feedback).

<a id="genagents"></a>**[GenAgents]** Park, J. S., et al. (2023).
*Generative Agents: Interactive Simulacra of Human Behavior.* arXiv:2304.03442.
https://arxiv.org/abs/2304.03442
— Agent architecture with observation, planning, and memory/reflection.

<a id="survey"></a>**[Survey]** Xi, Z., et al. (2023).
*The Rise and Potential of Large Language Model Based Agents: A Survey.*
arXiv:2309.07864. https://arxiv.org/abs/2309.07864
— Broad map of the agent field: brain / perception / action.

## Tools (how agents act on the world)

<a id="toolformer"></a>**[Toolformer]** Schick, T., et al. (2023).
*Toolformer: Language Models Can Teach Themselves to Use Tools.* arXiv:2302.04761.
https://arxiv.org/abs/2302.04761
— Models learning when and how to call external tools/APIs.

<a id="mcp"></a>**[MCP]** Anthropic (2024). *Model Context Protocol* (specification).
https://modelcontextprotocol.io
— An open standard for connecting tools and data sources to agents uniformly.

## Memory, retrieval, and embeddings

<a id="rag"></a>**[RAG]** Lewis, P., et al. (2020).
*Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.*
arXiv:2005.11401. https://arxiv.org/abs/2005.11401
— Fetch relevant facts and feed them into the prompt instead of guessing.

<a id="word2vec"></a>**[word2vec]** Mikolov, T., et al. (2013).
*Efficient Estimation of Word Representations in Vector Space.* arXiv:1301.3781.
https://arxiv.org/abs/1301.3781
— The idea that meaning can be represented as vectors.

<a id="sbert"></a>**[SBERT]** Reimers, N., & Gurevych, I. (2019).
*Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* arXiv:1908.10084.
https://arxiv.org/abs/1908.10084
— Sentence-level embeddings for semantic similarity search (what `find_similar_replies` will use).

## Safety: prompt injection & guardrails

<a id="injection"></a>**[Injection]** Greshake, K., et al. (2023).
*Not What You've Signed Up For: Compromising Real-World LLM-Integrated
Applications with Indirect Prompt Injection.* arXiv:2302.12173.
https://arxiv.org/abs/2302.12173
— Why you must never mix untrusted data with instructions.

<a id="owasp"></a>**[OWASP-LLM]** OWASP (2023–).
*OWASP Top 10 for Large Language Model Applications* (LLM01: Prompt Injection).
https://owasp.org/www-project-top-10-for-large-language-model-applications/
— Industry-standard catalogue of LLM application risks.

## Practitioner guidance

<a id="anthropic-agents"></a>**[Anthropic-Agents]** Anthropic (2024).
*Building Effective Agents.*
https://www.anthropic.com/research/building-effective-agents
— Argues for simple, composable patterns over heavy frameworks, and defines the
*workflow* vs *agent* distinction this project's design follows.

---

## How to cite this project's design

If you're writing about the Email Agent itself, the design rationale lives in the
sibling docs: [architecture](../02-architecture.md), [tech stack](../03-tech-stack.md)
(decision records DR-1…DR-9), and [data model](../04-data-model.md).
