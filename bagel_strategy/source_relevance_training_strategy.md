# 🎯 Source Relevance & Query Optimization Training Strategy

## 🔍 Core Training Objectives

### 1. **Most Relevant Source Selection**
**Goal:** Train Bagel RL to consistently identify and prioritize the highest-value legal sources for any given query.

#### Training Approach:
```python
# Example Training Scenario
{
  "scenario": "constitutional_law_research",
  "query": "First Amendment religious freedom workplace discrimination",
  "expert_source_ranking": [
    {"source": "supreme_court_cases", "relevance": 0.95, "authority": "binding"},
    {"source": "circuit_court_splits", "relevance": 0.90, "authority": "persuasive_high"},
    {"source": "eeoc_guidance", "relevance": 0.85, "authority": "administrative"},
    {"source": "law_review_articles", "relevance": 0.60, "authority": "secondary"},
    {"source": "blog_posts", "relevance": 0.20, "authority": "minimal"}
  ],
  "optimal_tools": [
    "select_optimal_databases(['supreme_court', 'circuit_courts', 'eeoc'])",
    "rank_source_relevance(['authority', 'factual_similarity', 'recency'])",
    "filter_jurisdiction(['federal', 'employment_specific'])"
  ]
}
```

#### Key Training Elements:
- **Authority Hierarchy Learning**: Supreme Court > Circuit Courts > District Courts > Administrative > Secondary
- **Jurisdiction Matching**: Federal vs. State law applicability
- **Practice Area Specialization**: Employment law sources vs. General constitutional sources
- **Factual Pattern Recognition**: Similar fact patterns = higher relevance
- **Temporal Relevance**: Recent developments vs. Established precedent balance

### 2. **Query Optimization Intelligence**

#### Smart Query Enhancement Training:
```python
{
  "original_query": "employee fired for religion",
  "query_analysis": {
    "legal_concepts": ["religious_discrimination", "wrongful_termination", "title_vii"],
    "jurisdiction_hints": [],
    "practice_area": "employment_law",
    "sophistication_level": "basic"
  },
  "optimized_queries": [
    {
      "database": "case_law",
      "query": "(religious discrimination OR religious accommodation) AND (workplace OR employment) AND (Title VII OR First Amendment)",
      "reasoning": "Boolean logic for comprehensive case law search"
    },
    {
      "database": "statutes",
      "query": "42 USC 2000e religious accommodation undue hardship",
      "reasoning": "Specific statutory provision search"
    },
    {
      "database": "regulations", 
      "query": "29 CFR 1605 religious practices workplace",
      "reasoning": "EEOC regulatory guidance on religious accommodation"
    }
  ]
}
```

#### Query Optimization Strategies:
- **Legal Concept Expansion**: "fired" → "termination", "discharge", "dismissal"
- **Synonym Integration**: "religion" → "religious beliefs", "faith", "creed"
- **Boolean Logic Construction**: Strategic AND/OR combinations
- **Citation-Specific Searches**: Direct statute/regulation targeting
- **Jurisdiction Inference**: Infer relevant jurisdictions from context

### 3. **Cross-Platform AI Integration Training**

#### Integrated Workflow Scenarios:
```python
{
  "workflow": "new_employment_case_intake",
  "trigger": "Client consultation: Religious discrimination claim",
  "integrated_tool_sequence": [
    # Research Phase
    "optimize_search_query(religious_discrimination_employment)",
    "select_optimal_databases(['eeoc_cases', 'circuit_courts', 'title_vii_guidance'])",
    "rank_source_relevance(['binding_precedent', 'factual_similarity'])",
    
    # Case Management Phase  
    "calculate_legal_deadlines(['eeoc_filing', 'right_to_sue', 'statute_limitations'])",
    "assess_resource_requirements(['discovery_scope', 'expert_witnesses'])",
    "optimize_scheduling_conflicts(['court_deadlines', 'client_availability'])",
    
    # Document Phase
    "classify_document_complexity(['employment_records', 'witness_statements'])",
    "generate_client_reports(['case_assessment', 'litigation_prospects'])",
    
    # Analytics Phase
    "generate_practice_insights(['similar_case_outcomes', 'settlement_patterns'])"
  ],
  "success_metrics": {
    "research_efficiency": "time_to_relevant_sources < 15_minutes",
    "case_setup_speed": "intake_to_strategy < 2_hours", 
    "client_satisfaction": "understanding_score > 4.5/5"
  }
}
```

## 📊 Training Data Generation Strategy

### 1. **Expert-Labeled Source Relevance Dataset**
```python
# Generate 10,000+ scenarios with expert rankings
{
  "query": "patent claim construction markman hearing",
  "expert_evaluation": {
    "most_relevant": [
      {"source": "federal_circuit_cases", "score": 0.95},
      {"source": "district_court_markman_orders", "score": 0.90},
      {"source": "patent_trial_practice_guides", "score": 0.75}
    ],
    "least_relevant": [
      {"source": "state_court_cases", "score": 0.10},
      {"source": "general_civil_procedure", "score": 0.15}
    ],
    "reasoning": "Federal Circuit has exclusive jurisdiction over patent appeals, Markman hearings are claim construction specific"
  }
}
```

### 2. **Query Optimization Training Pairs**
```python
{
  "training_pairs": [
    {
      "user_input": "Can my boss make me work Sundays?",
      "legal_translation": "religious accommodation workplace scheduling Title VII",
      "optimized_search": "religious accommodation AND (scheduling OR work schedule) AND (Title VII OR EEOC) AND (undue hardship OR reasonable accommodation)"
    },
    {
      "user_input": "Trademark infringement logo similar",
      "legal_translation": "trademark likelihood confusion visual similarity",
      "optimized_search": "(likelihood of confusion OR consumer confusion) AND (trademark infringement OR trademark violation) AND (visual similarity OR design similarity)"
    }
  ]
}
```

### 3. **Multi-Tool Workflow Training**
```python
{
  "complex_scenarios": [
    {
      "scenario": "class_action_employment_case",
      "phases": {
        "research": ["optimize_query", "select_databases", "rank_relevance"],
        "case_management": ["calculate_deadlines", "resource_allocation"],
        "discovery": ["document_classification", "evidence_analysis"], 
        "scheduling": ["court_deadlines", "deposition_coordination"],
        "client_communication": ["status_updates", "settlement_discussions"]
      },
      "success_criteria": {
        "research_quality": "relevant_sources_found / total_sources > 0.80",
        "efficiency": "time_to_case_strategy < 4_hours",
        "client_satisfaction": "communication_clarity > 4.0/5"
      }
    }
  ]
}
```

## 🎯 Specific Training Scenarios

### **Scenario 1: Legal Research Optimization**
```python
{
  "name": "constitutional_criminal_procedure",
  "user_query": "Fourth Amendment search warrant exceptions vehicles",
  "learning_objectives": [
    "Prioritize Supreme Court cases over lower courts",
    "Identify vehicle-specific Fourth Amendment precedents",
    "Balance historical foundation cases with recent developments",
    "Recognize circuit splits requiring Supreme Court resolution"
  ],
  "optimal_tool_sequence": [
    "optimize_search_query(['Fourth Amendment', 'vehicle searches', 'warrant exceptions'])",
    "select_optimal_databases(['supreme_court', 'circuit_courts', 'criminal_procedure_guides'])",
    "rank_source_relevance([
      {'criteria': 'binding_precedent', 'weight': 0.4},
      {'criteria': 'factual_similarity', 'weight': 0.3}, 
      {'criteria': 'recency', 'weight': 0.3}
    ])"
  ],
  "expected_top_sources": [
    "Carroll v. United States (foundational vehicle exception)",
    "Riley v. California (digital search limits)",
    "Rodriguez v. United States (traffic stop duration)",
    "Recent circuit court decisions on technology searches"
  ]
}
```

### **Scenario 2: Cross-Feature Integration**
```python
{
  "name": "patent_litigation_workflow",
  "trigger": "New patent infringement case filed",
  "integrated_workflow": [
    # Research Phase
    {
      "tools": ["optimize_search_query", "select_optimal_databases"],
      "goal": "Find relevant claim construction and infringement precedents"
    },
    # Deadline Management
    {
      "tools": ["calculate_legal_deadlines", "optimize_scheduling_conflicts"],
      "goal": "Set up critical patent litigation deadlines and court appearances"
    },
    # Document Analysis
    {
      "tools": ["classify_document_complexity", "extract_key_provisions"],
      "goal": "Analyze patent claims and accused products"
    },
    # Evidence Planning
    {
      "tools": ["classify_evidence_type", "select_forensic_analysis_tools"],
      "goal": "Plan technical evidence and expert witness strategy"
    },
    # Client Communication
    {
      "tools": ["personalize_communication_style", "generate_client_reports"],
      "goal": "Explain complex patent concepts to client"
    }
  ],
  "success_metrics": {
    "research_relevance": "> 85% relevant sources in top 10 results",
    "deadline_accuracy": "100% compliance with court deadlines",
    "client_comprehension": "> 4.5/5 client understanding score"
  }
}
```

### **Scenario 3: Source Authority Recognition**
```python
{
  "name": "securities_law_research",
  "query": "insider trading rule 10b-5 materiality standard",
  "authority_training": {
    "tier_1_sources": [
      {"source": "supreme_court_cases", "examples": ["Basic Inc. v. Levinson", "TSC Industries"]},
      {"source": "sec_releases", "examples": ["Release 34-40959", "Staff guidance"]},
      {"source": "circuit_court_precedents", "examples": ["Second Circuit", "Ninth Circuit"]}
    ],
    "tier_2_sources": [
      {"source": "district_court_decisions", "note": "persuasive but not binding"},
      {"source": "sec_enforcement_actions", "note": "practical guidance"},
      {"source": "no_action_letters", "note": "specific fact situations"}
    ],
    "avoid_sources": [
      {"source": "blog_commentary", "reason": "not_authoritative"},
      {"source": "student_notes", "reason": "academic_only"}
    ]
  },
  "ranking_logic": "Supreme Court > SEC > Circuit Courts > District Courts > Administrative > Secondary"
}
```

## 📈 Evaluation & Improvement Framework

### **Relevance Scoring System**
```python
{
  "evaluation_metrics": {
    "source_relevance": {
      "measurement": "expert_rating_correlation",
      "target": "> 0.90 correlation with expert rankings",
      "methodology": "blind evaluation by 3+ legal experts"
    },
    "query_optimization": {
      "measurement": "retrieval_effectiveness", 
      "target": "> 80% relevant results in top 10",
      "methodology": "precision@10 and recall measurements"
    },
    "workflow_efficiency": {
      "measurement": "time_to_completion",
      "target": "50% reduction in research time",
      "methodology": "before/after Bagel implementation comparison"
    },
    "user_satisfaction": {
      "measurement": "attorney_feedback_scores",
      "target": "> 4.5/5 average satisfaction",
      "methodology": "post-research survey and interviews"
    }
  }
}
```

### **Continuous Learning Integration**
```python
{
  "feedback_loops": {
    "user_ratings": {
      "implementation": "thumbs_up_down on each source",
      "weighting": "recent_feedback > historical_feedback",
      "threshold": "retrain_after_1000_new_ratings"
    },
    "outcome_tracking": {
      "implementation": "track_case_outcomes_vs_sources_used",
      "analysis": "winning_cases_source_patterns",
      "adjustment": "boost_sources_correlated_with_success"
    },
    "efficiency_monitoring": {
      "implementation": "time_tracking_per_research_task",
      "optimization": "identify_bottlenecks_in_tool_sequence",
      "improvement": "streamline_slow_workflows"
    }
  }
}
```

## 🚀 Implementation Roadmap

### **Phase 1: Foundation Training (Weeks 1-2)**
- Source authority recognition
- Basic query optimization
- Single-tool effectiveness

### **Phase 2: Integration Training (Weeks 3-4)**
- Multi-tool workflows
- Cross-feature coordination
- Complex legal scenarios

### **Phase 3: Optimization Training (Weeks 5-6)**
- User feedback integration
- Performance refinement
- Edge case handling

### **Phase 4: Production Deployment (Week 7)**
- A/B testing against current system
- Gradual rollout to users
- Continuous monitoring and improvement

This training strategy ensures Bagel RL learns to consistently identify the most relevant sources and optimize every aspect of legal practice management!