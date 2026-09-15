# from __future__ import annotations

# import logging
# from pathlib import Path

# from langgraph.graph import END, StateGraph

# from .aggregation_agent import AggregationAgent
# from .categorization_agent import CategorizationAgent
# from .db_storage_agent import DBStorageAgent
# from .extraction_agent import ExtractionAgent
# from .gemini_agent import GeminiAgent
# from .ocr_agent import OCRAgent
# from .types import AgentState
# from .validation_agent import ValidationAgent


# class SupervisorAgent:
#     name = "Supervisor Agent"

#     def __init__(self, settings, session_factory, logger=None):
#         self.settings = settings
#         self.log = logger or logging.getLogger("bill_agent")
#         self.gemini = GeminiAgent(settings)
#         self.ocr = OCRAgent(settings)
#         self.extract = ExtractionAgent()
#         self.validate = ValidationAgent()
#         self.cat = CategorizationAgent(settings.CATEGORY_CONFIG_PATH, self.gemini)
#         self.store = DBStorageAgent(session_factory)
#         self.agg = AggregationAgent(session_factory)
#         self.graph = self._build_graph()
       

#     def _build_graph(self):
#         graph = StateGraph(AgentState)
#         graph.add_node("ocr", self.ocr_node)
#         graph.add_node("extract", self.extract_node)
#         graph.add_node("llm_correct", self.llm_correct_node)
#         graph.add_node("validate", self.validate_node)
#         graph.add_node("llm_recheck", self.llm_recheck_node)
#         graph.add_node("categorize", self.categorize_node)
#         graph.add_node("store", self.store_node)
#         graph.add_node("aggregate", self.aggregate_node)
#         graph.add_node("reject", self.reject_node)

#         graph.set_entry_point("ocr")
#         graph.add_edge("ocr", "extract")
#         graph.add_edge("extract", "llm_correct")
#         graph.add_edge("llm_correct", "validate")
#         graph.add_conditional_edges(
#             "validate",
#             self.validation_router,
#             {"recheck": "llm_recheck", "categorize": "categorize", "reject": "reject"},
#         )
#         graph.add_edge("llm_recheck", "validate")
#         graph.add_edge("categorize", "store")
#         graph.add_edge("store", "aggregate")
#         graph.add_edge("aggregate", END)
#         graph.add_edge("reject", END)
#         return graph.compile()
    
#     def run_file(self, path: Path):
#         return self.graph.invoke({
#             "source_file": path.name,
#             "file_bytes": path.read_bytes(),
#             "gemini_used": False,
#             "gemini_calls": 0,
#             "was_duplicate": False,
#             "error": None,
#         })

#     def ocr_node(self, state):
#         self.log.info("[OCR Agent] file=%s status=start engine=RapidOCR", state["source_file"])
#         text, confidence = self.ocr.run(state["source_file"], state["file_bytes"])
#         if not text.strip():
#             raise ValueError("OCR returned no text")
#         return {**state, "ocr_text": text, "ocr_confidence": confidence}

#     def extract_node(self, state):
#         extracted = self.extract.run(state["ocr_text"])
#         self.log.info("[Extraction Agent] file=%s status=local_complete", state["source_file"])
#         return {**state, "local_extracted": extracted, "extracted": extracted}

#     def llm_correct_node(self, state):
#         calls = int(state.get("gemini_calls", 0))
#         # Gemini receives every local extraction so it can correct OCR/parser errors before validation.
#         # The per-file cap still protects free-tier usage and retries.
#         should_call = self.gemini.enabled and calls < self.settings.GEMINI_MAX_CALLS_PER_FILE
#         if not should_call:
#             return state

#         corrected = self.gemini.correct_extraction(
#             state["extracted"], state["ocr_text"], state["file_bytes"], state["source_file"]
#         )
#         merged = dict(state["extracted"])
#         for key, value in corrected.items():
#             if value not in (None, ""):
#                 merged[key] = value
#         self.log.info("[Gemini Extraction Agent] file=%s status=corrected", state["source_file"])
#         return {**state, "extracted": merged, "gemini_used": True, "gemini_calls": calls + 1}

#     def validate_node(self, state):
#         status, notes = self.validate.run(state["extracted"], state["ocr_confidence"])
#         self.log.info("[Validation Agent] file=%s status=%s notes=%s", state["source_file"], status, len(notes))
#         return {**state, "validation_status": status, "validation_notes": notes}

#     def validation_router(self, state):
#         status = state["validation_status"]
#         calls = int(state.get("gemini_calls", 0))
#         if status == "valid" or status == "warning":
#             return "categorize"
#         if self.gemini.enabled and calls < self.settings.GEMINI_MAX_CALLS_PER_FILE:
#             return "recheck"
#         return "reject"

#     def llm_recheck_node(self, state):
#         corrected = self.gemini.validate_correction(
#             state["extracted"], state["validation_notes"], state["ocr_text"]
#         )
#         merged = dict(state["extracted"])
#         for key, value in corrected.items():
#             if value not in (None, ""):
#                 merged[key] = value
#         calls = int(state.get("gemini_calls", 0)) + 1
#         self.log.info("[Gemini Extraction Agent] file=%s status=rechecked", state["source_file"])
#         return {**state, "extracted": merged, "gemini_used": True, "gemini_calls": calls}

#     def categorize_node(self, state):
#         category = self.cat.run(state["extracted"], state["ocr_text"])
#         self.log.info("[Categorization Agent] file=%s category=%s", state["source_file"], category)
#         return {**state, "category": category}

#     def store_node(self, state):
#         self.log.info("[DB Storage Agent] file=%s status=start", state["source_file"])
#         return self.store.run(state)

#     def aggregate_node(self, state):
#         self.log.info("[Aggregation Agent] file=%s status=start", state["source_file"])
#         return self.agg.run(state)

#     def reject_node(self, state):
#         self.log.warning("[Supervisor Agent] file=%s status=rejected notes=%s", state["source_file"], state.get("validation_notes"))
#         return {**state, "error": "Validation failed; bill was not stored."}  


from __future__ import annotations

import logging
from pathlib import Path

from langgraph.graph import END, StateGraph

from .aggregation_agent import AggregationAgent
from .categorization_agent import CategorizationAgent
from .db_storage_agent import DBStorageAgent
from .extraction_agent import ExtractionAgent
from .gemini_agent import GeminiAgent
from .ocr_agent import OCRAgent
from .types import AgentState
from .validation_agent import ValidationAgent


class SupervisorAgent:
    name = "Supervisor Agent"

    def __init__(self, settings, session_factory, logger=None):
        self.settings = settings
        self.log = logger or logging.getLogger("bill_agent")

        self.gemini = GeminiAgent(settings)
        self.ocr = OCRAgent(settings)
        self.extract = ExtractionAgent()
        self.validate = ValidationAgent()
        self.cat = CategorizationAgent(
            settings.CATEGORY_CONFIG_PATH,
            self.gemini
        )
        self.store = DBStorageAgent(session_factory)
        self.agg = AggregationAgent(session_factory)

        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)

        graph.add_node("ocr", self.ocr_node)
        graph.add_node("extract", self.extract_node)
        graph.add_node("llm_correct", self.llm_correct_node)
        graph.add_node("validate", self.validate_node)
        graph.add_node("llm_recheck", self.llm_recheck_node)
        graph.add_node("categorize", self.categorize_node)
        graph.add_node("store", self.store_node)
        graph.add_node("aggregate", self.aggregate_node)
        graph.add_node("reject", self.reject_node)

        graph.set_entry_point("ocr")

        graph.add_edge("ocr", "extract")
        graph.add_edge("extract", "llm_correct")
        graph.add_edge("llm_correct", "validate")

        graph.add_conditional_edges(
            "validate",
            self.validation_router,
            {
                "recheck": "llm_recheck",
                "categorize": "categorize",
                "reject": "reject",
            },
        )

        graph.add_edge("llm_recheck", "validate")
        graph.add_edge("categorize", "store")
        graph.add_edge("store", "aggregate")
        graph.add_edge("aggregate", END)
        graph.add_edge("reject", END)

        return graph.compile()

    def run_file(self, path: Path):
        return self.graph.invoke(
            {
                "source_file": path.name,
                "file_bytes": path.read_bytes(),
                "gemini_used": False,
                "gemini_calls": 0,
                "was_duplicate": False,
                "error": None,
            }
        )

    def ocr_node(self, state):
        self.log.info(
            "[OCR Agent] file=%s status=start engine=RapidOCR",
            state["source_file"],
        )

        text, confidence = self.ocr.run(
            state["source_file"],
            state["file_bytes"],
        )

        if not text.strip():
            raise ValueError("OCR returned no text")

        return {
            **state,
            "ocr_text": text,
            "ocr_confidence": confidence,
        }

    def extract_node(self, state):
        extracted = self.extract.run(
            state["ocr_text"]
        )

        self.log.info(
            "[Extraction Agent] file=%s status=local_complete",
            state["source_file"],
        )

        return {
            **state,
            "local_extracted": extracted,
            "extracted": extracted,
        }

    def llm_correct_node(self, state):
        calls = int(
            state.get("gemini_calls", 0)
        )

        # Gemini receives the local extraction so it can
        # correct OCR/parser errors before validation.
        should_call = (
            self.gemini.enabled
            and calls < self.settings.GEMINI_MAX_CALLS_PER_FILE
        )

        if not should_call:
            return state

        corrected = self.gemini.correct_extraction(
            state["extracted"],
            state["ocr_text"],
            state["file_bytes"],
            state["source_file"],
        )

        merged = dict(state["extracted"])

        for key, value in corrected.items():
            if value not in (None, ""):
                merged[key] = value

        self.log.info(
            "[Gemini Extraction Agent] file=%s status=corrected",
            state["source_file"],
        )

        return {
            **state,
            "extracted": merged,
            "gemini_used": True,
            "gemini_calls": calls + 1,
        }

    def validate_node(self, state):
        status, notes = self.validate.run(
            state["extracted"],
            state["ocr_confidence"],
        )

        self.log.info(
            "[Validation Agent] file=%s status=%s notes=%s",
            state["source_file"],
            status,
            len(notes),
        )

        return {
            **state,
            "validation_status": status,
            "validation_notes": notes,
        }

    def validation_router(self, state):
        status = state["validation_status"]
        calls = int(
            state.get("gemini_calls", 0)
        )

        if status in ("valid", "warning"):
            return "categorize"

        if (
            self.gemini.enabled
            and calls < self.settings.GEMINI_MAX_CALLS_PER_FILE
        ):
            return "recheck"

        return "reject"

    def llm_recheck_node(self, state):
        corrected = self.gemini.validate_correction(
            state["extracted"],
            state["validation_notes"],
            state["ocr_text"],
        )

        merged = dict(state["extracted"])

        for key, value in corrected.items():
            if value not in (None, ""):
                merged[key] = value

        calls = int(
            state.get("gemini_calls", 0)
        ) + 1

        self.log.info(
            "[Gemini Extraction Agent] file=%s status=rechecked",
            state["source_file"],
        )

        return {
            **state,
            "extracted": merged,
            "gemini_used": True,
            "gemini_calls": calls,
        }

    def categorize_node(self, state):
        category = self.cat.run(
            state["extracted"],
            state["ocr_text"],
        )

        self.log.info(
            "[Categorization Agent] file=%s category=%s",
            state["source_file"],
            category,
        )

        return {
            **state,
            "category": category,
        }

    def store_node(self, state):
        self.log.info(
            "[DB Storage Agent] file=%s status=start",
            state["source_file"],
        )

        return self.store.run(state)

    def aggregate_node(self, state):
        self.log.info(
            "[Aggregation Agent] file=%s status=start",
            state["source_file"],
        )

        return self.agg.run(state)

    def reject_node(self, state):
        self.log.warning(
            "[Supervisor Agent] file=%s status=rejected notes=%s",
            state["source_file"],
            state.get("validation_notes"),
        )

        return {
            **state,
            "error": "Validation failed; bill was not stored.",
        }
# ============================================================
# SEPARATE GRAPH DISPLAY + SAVE AS JPG
# ============================================================

def display_graph(supervisor):
    """
    Display the LangGraph Mermaid diagram and save it as JPG.
    """

    from IPython.display import display, Markdown
    import subprocess
    from pathlib import Path

    # Get Mermaid code
    mermaid_code = supervisor.graph.get_graph().draw_mermaid()

    # Display in Jupyter/IPython
    display(Markdown(mermaid_code))

    # Save Mermaid source
    mmd_file = Path("agent_graph.mmd")
    mmd_file.write_text(mermaid_code, encoding="utf-8")

    # Convert Mermaid → SVG using mermaid-cli
    svg_file = Path("agent_graph.svg")

    subprocess.run(
        [
            "mmdc",
            "-i",
            str(mmd_file),
            "-o",
            str(svg_file),
        ],
        check=True,
    )

    # Convert SVG → JPG using Pillow
    from PIL import Image
    import cairosvg

    png_file = Path("agent_graph.png")
    jpg_file = Path("agent_graph.jpg")

    cairosvg.svg2png(
        url=str(svg_file),
        write_to=str(png_file),
        background_color="white",
    )

    image = Image.open(png_file).convert("RGB")
    image.save(jpg_file, "JPEG", quality=95)

    print(f"Graph saved to: {jpg_file.absolute()}")