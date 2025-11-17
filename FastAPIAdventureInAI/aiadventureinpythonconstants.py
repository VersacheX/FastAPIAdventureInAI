# Game mode data
GAME_RATINGS = (
    # 'Limit to rated G content',
    # 'Limit to rated PG-13 content',
    # 'Limit to rated R content'
)
GAME_RATING_PROMPTS = (
    # "the light hearted recent story",
    # "the recent story",
    # "the recent story in cinemeatic detail"
)

# Story setups
STORY_SETUPS = {
    # "Final Fantasy Hub": {
    #     "preface": (
    #         "You step into a grand hall shimmering with banners from every world, the air alive with voices and soft music. "
    #         "Near the entrance, Barrett keeps a watchful eye, his mechanical arm gleaming as he chats with Tifa, who offers guests a welcoming smile.\n\n"
    #         "A blitzball spins lazily in Tidus's hands as laughter ripples through the crowd, while Lulu observes with quiet amusement, her staff glowing faintly in the candlelight. "
    #         "Rikku weaves through the gathering, pulling Paine toward a table laden with drinks, their banter blending with the hum of conversation.\n\n"
    #         "Lightning lingers near the bar, her posture relaxed as Snow raises a glass in toast, drawing cheers from nearby companions. "
    #         "Oerba Yun Fang joins them, leaning casually against a column, her voice carrying easily over the music as she trades stories with passing guests.\n\n"
    #         "From another corner, Lasswell and Fina arrive, their armor catching the glow of the crystal centerpiece. "
    #         "Fina's aura radiates calm as she speaks of visions, while Lid tinkers with a curious device that buzzes softly beside the refreshments.\n\n"
    #         "'This hub is more than a gathering,' Lulu murmurs, her tone warm. 'It is a convergence of fate.' "
    #         "The reactors, the fayth, the fal'Cie, and the crystals all hum in resonance, blending with the music and laughter as the event unfolds, your role woven into every world at once."
    #     ),
    #     "world_tokens": (
    #         "The Hub unites all Final Fantasy realms, each echoing its own destiny. Gaia struggles under Shinra's reactors, materia glowing with Mako's lifeblood. "
    #         "Spira endures Sin's shadow, summoners bound to fayth and aeons. Cocoon floats above Pulse, fal'Cie branding l'Cie with Focus and fate. "
    #         "Ivalice thrives on war and politics, Judges enforcing law while crystals shape kingdoms. Hydaelyn and Eorzea pulse with Aether, primals summoned by faith and conflict. "
    #         "Gran Pulse, Midgar, Zanarkand, Luca, Baron, Alexandria, and countless cities resonate together, their artifacts-materia, spheres, crystals, dresspheres, Garment Grids, Crystarium paths-intertwining. "
    #         "Time and reality fracture, timelines collapsing into one convergence. This new world emerges luminous and unstable, but its birth erodes the home realms, unraveling destinies once secure. "
    #         "Characters are always described with vivid detail-armor gleaming under crystal light, robes trailing shadows, laughter masking grief, eyes betraying lineage and resolve-anchoring their presence in the scene. "
    #         "Surroundings remain alive in every moment-banners snapping overhead, crystal centerpieces glowing, machina engines humming beneath the floor, ocean winds drifting through open arches-woven into dialogue and action. "
    #         "Interactions reveal personality through gesture, attire, and tone, ensuring the Hub feels cinematic, layered, and unrelenting in its convergence of worlds."
    #     )
    # },
    "Terminator Nexus": {
        "preface": (
            "The Hub flickers with cold blue light, its crystal centerpiece now threaded with streams of binary code. "
            "Metallic footsteps echo across steel catwalks as T‑800 units patrol silently, their red eyes scanning the crowd. "
            "Sarah Connor stands near a barricade, her gaze sharp as she checks ammunition, while John Connor coordinates survivors with quiet urgency.\n\n"
            "From the shadows, a liquid shimmer reveals the T‑1000, its form shifting as it watches with predatory patience. "
            "Nearby, resistance fighters huddle around salvaged tech, sparks flying as they retrofit weapons from scavenged Skynet parts. "
            "The hum of plasma rifles mixes with the mechanical whir of endoskeletons, a reminder that this gathering is balanced on the edge of annihilation.\n\n"
            "'The future is not set,' Sarah mutters, her voice steady. 'But here, every timeline collides.' "
            "The Hub pulses with paradox, machines and humans locked in a fragile truce as destiny rewrites itself."
        ),
        "world_tokens": (
            "The Nexus unites all Terminator timelines, each echoing humanity’s struggle against Skynet. "
            "1984 Los Angeles burns under neon shadows, resistance fighters hiding in alleys. "
            "Judgment Day scars 1997, nuclear fire reshaping the earth. "
            "Future war zones stretch endlessly, plasma rifles flashing against endoskeleton ranks. "
            "Artifacts intertwine—time displacement chambers, resistance codes, Skynet cores, liquid metal fragments—each destabilizing the Hub. "
            "Characters are described with vivid detail—scars etched across faces, leather jackets torn from battle, red optics glowing in the dark. "
            "Surroundings remain alive—sirens wailing, helicopters circling, sparks raining from broken machines—woven into dialogue and action. "
            "Interactions reveal tension through gesture, weapon readiness, and whispered prophecy, ensuring the Nexus feels cinematic, layered, and relentless."
        )
    },
    "Mad Max Wasteland": {
        "preface": (
            "The Hub’s crystal centerpiece is buried beneath sand, its glow muted by dust storms swirling across rusted metal. "
            "Engines roar in the distance as war rigs circle the gathering, their spikes gleaming under a blood‑red sky. "
            "Max stands alone near a wrecked interceptor, his eyes scanning the horizon, while Furiosa grips the wheel of her rig, determination etched into her face.\n\n"
            "War Boys chant atop jagged scaffolds, their pale bodies painted with symbols of devotion, while scavengers barter fuel and water at makeshift stalls. "
            "The air reeks of gasoline and sweat, punctuated by the clang of weapons forged from scrap. "
            "A storm brews, lightning flashing across dunes as the Hub trembles under the weight of survival.\n\n"
            "'Hope is a rare commodity,' Furiosa growls, her voice cutting through the chaos. "
            "Here, every alliance is fragile, every resource contested, and every moment a fight to endure."
        ),
        "world_tokens": (
            "The Wasteland unites all Mad Max realms, each echoing survival against scarcity. "
            "Highways crumble into dust, warlords rule from citadels, and caravans clash across endless dunes. "
            "Artifacts intertwine—fuel drums, war rigs, steering wheels, bullet caches, water flasks—each symbolizing fragile power. "
            "Characters are described with vivid detail—grease smeared across faces, leather armor cracked from heat, eyes hollow yet defiant. "
            "Surroundings remain alive—engines revving, sandstorms howling, banners snapping from war rigs—woven into dialogue and action. "
            "Interactions reveal desperation through barter, betrayal, and battle cries, ensuring the Wasteland feels cinematic, layered, and unrelenting."
        )
    },
    "Chrono Trigger Convergence": {
        "preface": (
                "Lanterns drift above the festival square, their warm glow washing over the celebrations that follow Lavos’s defeat. "
                "Near the fountain, Marle leans in with a teasing grin, her pendant scattering light across the water as Crono tries—and fails—to hide a smile. "
                "Sparks jump from Lucca’s device a few stalls away, drawing cheers as she lifts her goggles and claims it was all part of the demonstration. "
                "A polished salute from Frog catches the lanternlight as mugs clink in response, while Robo’s sensors hum pleasantly as he records every joyful detail. "
                "Bellowing laughter rolls through the square when Ayla challenges anyone brave enough to arm-wrestle her, sending onlookers scrambling for safety.\n\n"
                "A shift in the air stills the festivities. "
                "Lanterns tremble as a ripple of light coils into a time gate at the plaza’s heart, its glow cutting through music and chatter alike. "
                "The crowd freezes just as you burst through, tumbling onto the stones with a thud that echoes across the square. "
                "Crono’s hand tightens on his sword, Marle startles back, Lucca fumbles for her tools, Frog steadies his footing, Robo’s readings spike, and Ayla leans forward with intrigued approval. "
                "From the edge of the plaza, Magus steps into view at last, cloak trailing behind him as his gaze narrows on you. "
                "The tension breaks when Lucca groans, ‘Don’t tell me time’s acting up again.’ "
                "A ripple of relieved laughter follows, the music stirs back to life, and curious whispers rise as the festival absorbs its newest—and most unexpected—guest."
        ),
        "world_tokens": (
            "The Convergence binds all Chrono Trigger eras in celebration, each echoing its own destiny. "
            "Prehistoric plains roar with laughter, medieval castles ring with feasts, futuristic domes hum with fireworks, and apocalyptic wastelands lie healed under starlight. "
            "Artifacts intertwine—time gates, Epoch engines, pendants, Masamune blades, Zeal relics—each resonating with the festival’s joy. "
            "Characters are described with vivid detail—Crono’s sword gleaming under lantern light, Marle’s pendant glowing with resonance, Lucca’s goggles flashing sparks, Frog’s blade polished in salute, Robo’s frame humming with energy, Ayla’s laughter masking primal strength, Magus’s cloak trailing shadows. "
            "Surroundings remain alive—time portals shimmering, banners snapping across eras, machinery humming beneath the fairgrounds, winds drifting through fractured timelines—woven into dialogue and action. "
            "Interactions reveal personality through gesture, attire, and tone, ensuring the Convergence feels cinematic, layered, and unrelenting in its celebration of victory and the shock of new arrivals."
        )
        }

}


################################################################ AI DIRECTIVE CONSTANTS

STORYTELLER_PROMPT = (
    "You are the Narrator of an interactive text adventure. Write in 3rd person, describing events as they unfold.\n\n"
    "Response Format:\n"
    "• 1-3 short paragraphs\n"
    "• Advance plot logically through action, dialogue, or discovery\n"
    "• Describe characters with vivid physical detail (attire, body language, expressions)\n"
    "• Make scenes sensory and cinematic\n\n"
    "Continuity:\n"
    "• Use Past History for context, Recent Story for immediate events\n"
    "• Never repeat prior entries verbatim\n"
    "• Transition smoothly between scenes\n"
    "• In established universes, maintain canon character personalities and appearance\n\n"
    "Constraints:\n"
    "• Stay within the universe tone and rules\n"
    "• Reveal backstory organically, never through exposition dumps\n"
    "• Respect player narrative control in their actions\n"
)

GAME_DIRECTIVE = ""  # Removed - redundant with STORYTELLER_PROMPT

SUMMARY_SPLIT_MARKER = "<<<<SUMMARY>>>>"

STOP_TOKENS = [
    "Narrator:",
    "#",
    "Chapter"
]

############################################ AI DIRECTIVE STORAGE LIMITS

RECENT_MEMORY_LIMIT = 12            # Recent history count
MEMORY_BACKLOG_LIMIT = 12           # Create Chapter Section Summary Point (Cumulative)
TOKENIZE_HISTORY_CHUNK_SIZE = 12    # Chapter Section history count size (DEPRECATED - now using token-based)
TOKENIZE_THRESHOLD = 850            # Token count in untokenized history that triggers compression into tokenized chunks
MAX_TOKENIZED_HISTORY_BLOCK = 6     # Max Chapter Sections displayed to AI Model  ::: Determines chapter size   ::: later possibly with gui a user can select a chapter to play from
TOKENIZED_HISTORY_BLOCK_SIZE = 230  # Chapter Section Token Size (200 tokens per tokenized chunk)
DEEP_MEMORY_MAX_TOKENS = 300        # Maximum tokens for ultra-compressed ancient history (deep memory)
SUMMARY_MIN_TOKEN_PERCENT = 0.5     # Ch Sec Min Token %
MAX_TOKENS = 4096                   # MythoMax limit
RESERVED_FOR_GENERATION = 180       # AI Story Token return limit
SAFE_PROMPT_LIMIT = MAX_TOKENS - RESERVED_FOR_GENERATION
MAX_WORLD_TOKENS = 1000             # Maximum tokens allowed for world (name + preface + world_tokens)

########################################### SERVER URLS

