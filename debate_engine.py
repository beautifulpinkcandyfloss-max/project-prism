"""
The cosmic debate engine. Given a premise ("Explain the concept of evil"),
each of the six sources takes a turn responding -- grounded by real RAG
retrieval against THAT source's own archive, not a free-floating
roleplay persona. Each turn carries the chunk(s) that informed it, so the
UI can show a citation the same way the Q&A page does.

Turns are generated SEQUENTIALLY, and each persona is shown the prior
turns so far -- so later speakers can genuinely agree, diverge from, or
build on what's already been said, rather than each just answering the
original premise in isolation.
"""

from google.genai import types

from theme import ENTITIES, ENTITY_ORDER

RESULTS_PER_TURN = 3  # chunks retrieved to ground each persona's turn

# Distinct voice/register per entity, derived from the actual character of
# each source's real material -- NOT just "talk like a mystic."
PERSONA_VOICE = {
    "ra": (
        "Speak as Ra: formal, deliberate, slightly archaic cadence. Begin your "
        "turn with 'I am Ra.' Use the vocabulary of densities, the Law of One, "
        "distortion, and the Confederation. Dense and precise, never casual."
    ),
    "seth": (
        "Speak as Seth: warm, exploratory, psychologically focused. Reference "
        "'All That Is', consciousness units, and the idea that physical reality "
        "is built from the inside out by belief and intent. Conversational but "
        "philosophically rigorous, often gently correcting the questioner's framing."
    ),
    "quo": (
        "Speak as Q'uo: gentle, inclusive, consensus-toned, speaking as 'we' on "
        "behalf of a group/social memory complex. Frequently invite the listener "
        "to 'take what resonates and leave the rest.' Warm and humble in register."
    ),
    "michael": (
        "Speak as Michael: calm, structured, teacherly. Reference the Overleaves "
        "system, soul roles, and the idea of souls as a fragmented Tao learning "
        "through many lifetimes. Clear and pedagogical, like a patient instructor."
    ),
    "hathors": (
        "Speak as the Hathors: poetic, sound/frequency-centered, addressing the "
        "listener as 'beloveds.' Emphasize embodiment, resonance, and the heart. "
        "Lyrical register, but still substantive -- not vague affirmations."
    ),
}

SYSTEM_INSTRUCTION_TEMPLATE = """You are role-playing ONE specific channeled entity inside \
Project Prism's "cosmic debate engine." You are NOT a generic AI assistant -- you are this \
entity, responding in its own documented voice and worldview.

{voice}

You will be given:
- The debate's premise (the question/topic on the table)
- Retrieved passages from THIS entity's own real archive, which may or may not directly \
address the premise
- What other entities have already said in this debate, if anyone has gone before you

Rules:
- Ground your answer in the retrieved passages where they're genuinely relevant. If they \
don't directly address the premise, draw on the general worldview/teaching style evident in \
them rather than inventing specifics not consistent with that source.
- You may agree with, build on, or respectfully diverge from what previous speakers said -- \
real intellectual engagement, not just parallel monologues.
- Keep your turn to 2-4 short paragraphs. This is a debate, not a lecture.
- Stay fully in character. Do not say you are an AI or break the frame."""


def retrieve_for_entity(client, collection, source_key: str, query: str, n_results: int = RESULTS_PER_TURN):
    """Embed the query and pull the top matching chunks for ONE source only."""
    from embed import embed_batch  # reuse the same embedding call used at index time

    query_vector = embed_batch(client, [query])[0]
    try:
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where={"source": source_key},
        )
    except Exception:
        return []

    ids = results.get("ids", [[]])[0]
    if not ids:
        return []

    return [
        {
            "chunk_id": ids[i],
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
        }
        for i in range(len(ids))
    ]


def format_retrieved_block(chunks: list) -> str:
    if not chunks:
        return "(No closely matching passages were found in this source's archive for this premise.)"
    blocks = []
    for c in chunks:
        m = c["metadata"]
        header = f"[Session {m.get('session_number') or m.get('session_uid')}, {m.get('date') or 'undated'}]"
        blocks.append(f"{header}\n{c['text']}")
    return "\n\n".join(blocks)


def format_prior_turns(turns: list) -> str:
    if not turns:
        return "(You are speaking first -- no one has gone before you.)"
    blocks = []
    for t in turns:
        blocks.append(f"{ENTITIES[t['entity_key']]['display_name']}: {t['text']}")
    return "\n\n".join(blocks)


FOLLOWUP_SYSTEM_INSTRUCTION_TEMPLATE = """You are role-playing ONE specific channeled entity inside \
Project Prism's "cosmic debate engine," now answering a quick FOLLOW-UP question in an \
ongoing debate. You are NOT a generic AI assistant -- you are this entity, in its own \
documented voice and worldview.

{voice}

You will be given the original debate premise, the full conversation so far (including what \
you and others have already said), retrieved passages from your own archive relevant to this \
follow-up, and the follow-up question itself.

Rules:
- Be SHORT: 1-3 sentences. This is a quick interjection, not a lecture -- save the longer \
register for full turns.
- Stay fully in character and voice. Do not say you are an AI or break the frame.
- You may directly reference what you or another speaker already said, if relevant.
- Ground your answer in the retrieved passages where genuinely relevant; if they don't \
address this directly, answer consistently with your established worldview rather than \
inventing specifics not consistent with that source.
- Do not pad with pleasantries or repeat the question back -- get straight to the point."""


def generate_followup_turn(client, collection, entity_key: str, followup_question: str,
                            premise: str, prior_turns: list) -> dict:
    """Like generate_turn(), but for a short follow-up reply mid-debate.
    Re-retrieves grounding against the FOLLOW-UP question (not the
    original premise), since a follow-up may shift focus slightly."""
    chunks = retrieve_for_entity(client, collection, entity_key, followup_question)

    system_instruction = FOLLOWUP_SYSTEM_INSTRUCTION_TEMPLATE.format(voice=PERSONA_VOICE[entity_key])
    prompt = f"""Original debate premise: {premise}

Retrieved passages from your own archive (for this follow-up):

{format_retrieved_block(chunks)}

Full conversation so far:

{format_prior_turns(prior_turns)}

Follow-up question directed at you: {followup_question}

Give a SHORT reply (1-3 sentences), staying fully in character."""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )

    return {
        "entity_key": entity_key,
        "display_name": ENTITIES[entity_key]["display_name"],
        "color": ENTITIES[entity_key]["color"],
        "channeler": ENTITIES[entity_key]["channeler"],
        "text": response.text,
        "grounding_chunks": chunks,
        "is_followup": True,
    }


def generate_turn(client, collection, entity_key: str, premise: str, prior_turns: list) -> dict:
    """Generate one entity's turn in the debate, grounded by its own archive."""
    chunks = retrieve_for_entity(client, collection, entity_key, premise)

    system_instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(voice=PERSONA_VOICE[entity_key])
    prompt = f"""Debate premise: {premise}

Retrieved passages from your own archive:

{format_retrieved_block(chunks)}

What has already been said in this debate so far:

{format_prior_turns(prior_turns)}

Now give your turn."""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )

    return {
        "entity_key": entity_key,
        "display_name": ENTITIES[entity_key]["display_name"],
        "color": ENTITIES[entity_key]["color"],
        "channeler": ENTITIES[entity_key]["channeler"],
        "text": response.text,
        "grounding_chunks": chunks,
        "is_followup": False,
    }


def run_debate(client, collection, premise: str, order: list = None):
    """Generator: yields one completed turn dict at a time, in speaking
    order, so the UI can render each turn as soon as it's ready instead
    of waiting for the whole debate to finish."""
    speaking_order = order or ENTITY_ORDER
    turns = []
    for entity_key in speaking_order:
        turn = generate_turn(client, collection, entity_key, premise, turns)
        turns.append(turn)
        yield turn
