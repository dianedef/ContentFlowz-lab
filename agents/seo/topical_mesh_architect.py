"""
Topical Mesh Architect Agent - Dedicated Topical SEO Analysis
Standalone agent for analyzing and designing topical mesh structures.

Implements French SEO "Cocon Sémantique" (Semantic Cocoon) methodology.

Responsibilities:
- Analyze existing website topical structure
- Design optimal topical mesh architecture
- Identify mesh weaknesses and gaps
- Generate strengthening plans
- Calculate topical authority scores
- Create visual mesh representations
"""
from typing import List, Optional, Dict, Any
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
import os
import json

from agents.shared.prompt_loader import load_prompt
from agents.seo.tools.strategy_tools import TopicalMeshBuilder
from agents.seo.tools.mesh_analyzer import ExistingMeshAnalyzer

load_dotenv()


class TopicalMeshArchitect:
    """
    Dedicated agent for topical mesh design and analysis.
    Implements French SEO "Cocon Sémantique" methodology.

    Use Cases:
    - Audit existing website topical structure
    - Design new topical mesh campaigns
    - Identify content gaps and opportunities
    - Optimize internal linking for authority flow
    - Benchmark topical authority vs competitors
    """

    def __init__(self, llm_model: str = "groq/mixtral-8x7b-32768"):
        """
        Initialize Topical Mesh Architect.

        Args:
            llm_model: LiteLLM model string (default: groq/mixtral-8x7b-32768)
                      Examples: "groq/llama-3.3-70b-versatile", "openai/gpt-4"
        """
        self.llm_model = llm_model
        self.mesh_builder = TopicalMeshBuilder()
        self.existing_analyzer = ExistingMeshAnalyzer()
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create the Topical Mesh Architect agent."""
        p = load_prompt("seo", "topical_mesh_architect")
        return Agent(
            role=p["role"],
            goal=p["goal"],
            backstory=p["backstory"],
            verbose=True,
            allow_delegation=False,
            llm=self.llm_model  # CrewAI uses LiteLLM internally
        )
    
    def analyze_topical_mesh(
        self,
        main_topic: str,
        subtopics: List[str],
        business_goals: Optional[List[str]] = None,
        competitor_topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive topical mesh analysis.
        
        Args:
            main_topic: Central topic to analyze
            subtopics: Related subtopics/cluster topics
            business_goals: Business objectives (rank/convert/inform)
            competitor_topics: Topics competitors are covering
            
        Returns:
            Complete mesh analysis with recommendations
        """
        # Build semantic cocoon
        mesh_structure = self.mesh_builder.build_semantic_cocoon(
            main_topic=main_topic,
            subtopics=subtopics,
            business_goals=business_goals
        )
        
        # Calculate authority
        authority_score = self.mesh_builder.calculate_topical_authority(mesh_structure)
        
        # Generate linking strategy
        linking_strategy = self.mesh_builder.optimize_internal_linking(mesh_structure)
        
        # Identify gaps (if competitor data provided)
        content_gaps = []
        if competitor_topics:
            our_topics = set([main_topic] + subtopics)
            their_topics = set(competitor_topics)
            missing_topics = their_topics - our_topics
            content_gaps = list(missing_topics)
        
        # Compile analysis
        analysis = {
            "main_topic": main_topic,
            "mesh_structure": mesh_structure,
            "topical_authority_score": authority_score,
            "authority_grade": self._get_authority_grade(authority_score),
            "linking_strategy": linking_strategy,
            "content_gaps": content_gaps,
            "mesh_health": self._assess_mesh_health(mesh_structure),
            "recommendations": self._generate_recommendations(
                mesh_structure,
                authority_score,
                content_gaps
            ),
            "quick_wins": self._identify_quick_wins(mesh_structure, linking_strategy)
        }
        
        return analysis
    
    def analyze_existing_website(
        self,
        repo_url: str,
        local_repo_path: Optional[str] = None,
        github_token: Optional[str] = None,
        force_update: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze existing website's topical mesh structure.

        Args:
            repo_url: GitHub repository URL
            local_repo_path: Explicit local path — skips git entirely (self-hosted)
            github_token: User's GitHub OAuth token from Clerk, for private repo cloning
            force_update: git pull when repo already cached on disk
        """
        return self.existing_analyzer.analyze_existing_website(
            repo_url,
            local_repo_path=local_repo_path,
            github_token=github_token,
            force_update=force_update,
        )
    
    def improve_existing_mesh(
        self,
        current_analysis: Dict[str, Any],
        new_topics: Optional[List[str]] = None,
        competitor_topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate improvement plan for existing mesh.
        
        Args:
            current_analysis: Output from analyze_existing_website()
            new_topics: New topics to add (optional)
            competitor_topics: Competitor topics for gap analysis (optional)
            
        Returns:
            Detailed improvement plan with projections
        """
        existing_mesh = current_analysis["existing_mesh"]
        current_authority = current_analysis["authority_score"]
        
        # Base improvement from fixing current issues
        base_plan = current_analysis["improvement_plan"]
        
        # Add new content recommendations
        if new_topics:
            new_content_impact = len(new_topics) * 5  # 5 points per topic
            base_plan["phase2"]["actions"].append(
                f"Create {len(new_topics)} new cluster pages: {', '.join(new_topics[:3])}"
            )
            base_plan["total_improvement"] += new_content_impact
            base_plan["final_projected_authority"] += new_content_impact
        
        # Add competitor gap analysis
        content_gaps = []
        if competitor_topics:
            existing_topics = [existing_mesh["pillar_page"].get("title", "")] + \
                            [c["title"] for c in existing_mesh.get("cluster_pages", [])]
            
            for comp_topic in competitor_topics:
                if not any(comp_topic.lower() in et.lower() for et in existing_topics):
                    content_gaps.append(comp_topic)
            
            if content_gaps:
                gap_impact = len(content_gaps) * 4
                base_plan["phase3"]["actions"].append(
                    f"Fill {len(content_gaps)} competitor gaps: {', '.join(content_gaps[:3])}"
                )
                base_plan["total_improvement"] += gap_impact
                base_plan["final_projected_authority"] += gap_impact
        
        return {
            "current_authority": current_authority,
            "improvement_plan": base_plan,
            "new_topics_added": new_topics or [],
            "content_gaps_identified": content_gaps,
            "final_projection": base_plan["final_projected_authority"],
            "estimated_timeline": "3-6 weeks for full implementation"
        }
    
    def compare_with_ideal(
        self,
        repo_url: str,
        ideal_main_topic: str,
        ideal_subtopics: List[str]
    ) -> Dict[str, Any]:
        """
        Compare existing website with ideal mesh structure.
        
        Args:
            repo_url: GitHub repository URL
            ideal_main_topic: Main topic for ideal mesh
            ideal_subtopics: Desired subtopics for ideal mesh
            
        Returns:
            Comparison analysis with gaps and recommendations
        """
        # Analyze existing
        existing_analysis = self.analyze_existing_website(repo_url)
        
        # Compare with ideal
        comparison = self.existing_analyzer.compare_with_ideal(
            existing_analysis["existing_mesh"],
            ideal_main_topic,
            ideal_subtopics
        )
        
        return {
            "existing_analysis": existing_analysis,
            "ideal_comparison": comparison,
            "recommendation": comparison["recommendation"],
            "action_items": self._generate_comparison_actions(comparison)
        }
    
    def _generate_comparison_actions(self, comparison: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate specific actions from comparison."""
        actions = []
        
        # Missing topics
        missing = comparison.get("missing_topics", [])
        if missing:
            for topic in missing[:5]:  # Top 5
                actions.append({
                    "action": f"Create new page: {topic}",
                    "priority": "HIGH",
                    "impact": "+5-8 authority points"
                })
        
        # Authority gap
        gap = comparison.get("authority_gap", 0)
        if gap > 20:
            actions.append({
                "action": "Major mesh restructuring needed",
                "priority": "HIGH",
                "impact": f"+{int(gap)} authority points potential"
            })
        elif gap > 10:
            actions.append({
                "action": "Strengthen existing content and add missing pieces",
                "priority": "MEDIUM",
                "impact": f"+{int(gap)} authority points potential"
            })
        
        # Density gap
        if comparison.get("ideal_density", 0) - comparison.get("current_density", 0) > 0.1:
            actions.append({
                "action": "Add strategic internal links",
                "priority": "MEDIUM",
                "impact": "+5-10 authority points"
            })
        
        return actions
    
    def design_mesh_from_scratch(
        self,
        main_topic: str,
        business_goals: List[str],
        target_pages: int = 10,
        industry: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Design a complete topical mesh from scratch.
        
        Args:
            main_topic: Central topic
            business_goals: Business objectives
            target_pages: Number of pages to plan (default: 10)
            industry: Industry context for topic generation
            
        Returns:
            Complete mesh design with implementation plan
        """
        # Generate subtopics (simulated - in production would use LLM/semantic analysis)
        subtopics = self._generate_subtopics(main_topic, target_pages - 1, industry)
        
        # Build mesh
        mesh_structure = self.mesh_builder.build_semantic_cocoon(
            main_topic=main_topic,
            subtopics=subtopics,
            business_goals=business_goals
        )
        
        # Calculate metrics
        authority_score = self.mesh_builder.calculate_topical_authority(mesh_structure)
        linking_strategy = self.mesh_builder.optimize_internal_linking(mesh_structure)
        
        # Create implementation plan
        implementation_plan = self._create_implementation_plan(
            mesh_structure,
            linking_strategy
        )
        
        design = {
            "main_topic": main_topic,
            "mesh_structure": mesh_structure,
            "topical_authority_score": authority_score,
            "linking_strategy": linking_strategy,
            "implementation_plan": implementation_plan,
            "estimated_timeline": self._estimate_timeline(target_pages),
            "success_metrics": self._define_success_metrics(main_topic, authority_score)
        }
        
        return design
    
    def audit_mesh_health(
        self,
        mesh_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Audit mesh health and identify weaknesses.
        
        Args:
            mesh_structure: Existing mesh structure
            
        Returns:
            Health audit with issues and fixes
        """
        health_score = 0
        issues = []
        fixes = []
        
        # Check mesh density
        density = mesh_structure.get("mesh_density", 0)
        if density < 0.3:
            issues.append({
                "type": "low_density",
                "severity": "HIGH",
                "description": f"Mesh density too low ({density:.2f}). Poor internal linking."
            })
            fixes.append({
                "issue": "low_density",
                "action": "Add cross-links between cluster pages",
                "priority": "HIGH",
                "estimated_impact": "+15 authority points"
            })
        else:
            health_score += 25
        
        # Check page count
        total_pages = mesh_structure.get("total_pages", 0)
        if total_pages < 5:
            issues.append({
                "type": "insufficient_coverage",
                "severity": "MEDIUM",
                "description": f"Only {total_pages} pages. Need more comprehensive coverage."
            })
            fixes.append({
                "issue": "insufficient_coverage",
                "action": "Create 5-10 more cluster pages",
                "priority": "MEDIUM",
                "estimated_impact": "+20 authority points"
            })
        else:
            health_score += 25
        
        # Check pillar strength
        pillar = mesh_structure.get("pillar_page", {})
        pillar_authority = pillar.get("authority_score", 0)
        if pillar_authority < 70:
            issues.append({
                "type": "weak_pillar",
                "severity": "HIGH",
                "description": f"Pillar authority only {pillar_authority}/100"
            })
            fixes.append({
                "issue": "weak_pillar",
                "action": "Add more internal links pointing to pillar",
                "priority": "HIGH",
                "estimated_impact": "+10 authority points"
            })
        else:
            health_score += 30
        
        # Check cluster distribution
        clusters = mesh_structure.get("cluster_pages", [])
        if len(clusters) > 0:
            avg_cluster_authority = sum(c.get("authority_score", 0) for c in clusters) / len(clusters)
            if avg_cluster_authority < 50:
                issues.append({
                    "type": "weak_clusters",
                    "severity": "MEDIUM",
                    "description": f"Average cluster authority only {avg_cluster_authority:.1f}/100"
                })
                fixes.append({
                    "issue": "weak_clusters",
                    "action": "Strengthen cluster content and internal links",
                    "priority": "MEDIUM",
                    "estimated_impact": "+12 authority points"
                })
            else:
                health_score += 20
        
        audit = {
            "health_score": health_score,
            "health_grade": self._get_health_grade(health_score),
            "issues_found": len(issues),
            "issues": issues,
            "fixes": fixes,
            "audit_summary": self._generate_audit_summary(health_score, issues)
        }
        
        return audit
    
    def generate_visual_report(
        self,
        analysis: Dict[str, Any],
        output_path: str = "data/topical_mesh_report.png"
    ) -> str:
        """
        Generate visual mesh report with NetworkX.
        
        Args:
            analysis: Output from analyze_topical_mesh
            output_path: Path for visualization
            
        Returns:
            Path to generated visualization
        """
        mesh_structure = analysis.get("mesh_structure", {})
        
        viz_path = self.mesh_builder.generate_mesh_visualization(
            mesh_structure=mesh_structure,
            output_path=output_path,
            output_format="png"
        )
        
        return viz_path
    
    # Private helper methods
    
    def _assess_mesh_health(self, mesh_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall mesh health."""
        density = mesh_structure.get("mesh_density", 0)
        total_pages = mesh_structure.get("total_pages", 0)
        total_links = mesh_structure.get("total_links", 0)
        
        health = {
            "density_status": "Good" if density >= 0.4 else "Needs Improvement",
            "coverage_status": "Good" if total_pages >= 7 else "Needs Expansion",
            "linking_status": "Good" if total_links >= 15 else "Needs More Links"
        }
        
        return health
    
    def _generate_recommendations(
        self,
        mesh_structure: Dict[str, Any],
        authority_score: float,
        content_gaps: List[str]
    ) -> List[Dict[str, str]]:
        """Generate strategic recommendations."""
        recommendations = []
        
        if authority_score < 60:
            recommendations.append({
                "priority": "HIGH",
                "action": "Strengthen mesh foundation",
                "details": "Add 3-5 more cluster pages and increase internal linking"
            })
        
        if content_gaps:
            recommendations.append({
                "priority": "MEDIUM",
                "action": f"Fill {len(content_gaps)} content gaps",
                "details": f"Create content for: {', '.join(content_gaps[:3])}"
            })
        
        if mesh_structure.get("mesh_density", 0) < 0.35:
            recommendations.append({
                "priority": "HIGH",
                "action": "Increase mesh density",
                "details": "Add cross-links between related cluster pages"
            })
        
        return recommendations
    
    def _identify_quick_wins(
        self,
        mesh_structure: Dict[str, Any],
        linking_strategy: List[Dict]
    ) -> List[Dict[str, str]]:
        """Identify quick win opportunities."""
        quick_wins = []
        
        # High-priority links
        high_priority_links = [l for l in linking_strategy if l.get("priority") == "HIGH"]
        if high_priority_links:
            quick_wins.append({
                "action": "Add high-priority internal links",
                "effort": "Low",
                "impact": "High",
                "count": len(high_priority_links)
            })
        
        # Expand thin clusters
        clusters = mesh_structure.get("cluster_pages", [])
        thin_clusters = [c for c in clusters if c.get("word_count", 0) < 1500]
        if thin_clusters:
            quick_wins.append({
                "action": "Expand thin cluster content",
                "effort": "Medium",
                "impact": "Medium",
                "count": len(thin_clusters)
            })
        
        return quick_wins
    
    def _generate_subtopics(
        self,
        main_topic: str,
        count: int,
        industry: Optional[str]
    ) -> List[str]:
        """Generate relevant subtopics (simulated)."""
        # In production, would use LLM or semantic analysis
        base_patterns = [
            f"{main_topic} for Beginners",
            f"Advanced {main_topic} Strategies",
            f"{main_topic} Best Practices",
            f"Common {main_topic} Mistakes",
            f"{main_topic} Tools and Resources",
            f"{main_topic} Case Studies",
            f"{main_topic} Trends and Updates",
            f"How to Implement {main_topic}",
            f"{main_topic} ROI Analysis",
            f"{main_topic} Checklist"
        ]
        
        return base_patterns[:count]
    
    def _create_implementation_plan(
        self,
        mesh_structure: Dict[str, Any],
        linking_strategy: List[Dict]
    ) -> Dict[str, Any]:
        """Create phased implementation plan."""
        total_pages = mesh_structure.get("total_pages", 0)
        
        phases = []
        
        # Phase 1: Foundation (Pillar + 3 clusters)
        phases.append({
            "phase": 1,
            "name": "Foundation",
            "duration_weeks": 2,
            "deliverables": ["Pillar page", "3 cluster pages", "Basic internal links"],
            "focus": "Establish core mesh structure"
        })
        
        # Phase 2: Expansion (4-7 clusters)
        if total_pages > 4:
            phases.append({
                "phase": 2,
                "name": "Expansion",
                "duration_weeks": 3,
                "deliverables": ["4-7 additional clusters", "Cross-linking", "Visual mesh"],
                "focus": "Build comprehensive coverage"
            })
        
        # Phase 3: Optimization (8+ clusters)
        if total_pages > 7:
            phases.append({
                "phase": 3,
                "name": "Optimization",
                "duration_weeks": 2,
                "deliverables": ["Remaining clusters", "Authority optimization", "Content updates"],
                "focus": "Maximize topical authority"
            })
        
        return {
            "phases": phases,
            "total_duration_weeks": sum(p["duration_weeks"] for p in phases),
            "total_pages": total_pages
        }
    
    def _estimate_timeline(self, page_count: int) -> str:
        """Estimate implementation timeline."""
        weeks = (page_count // 3) + 2
        return f"{weeks} weeks ({page_count} pages)"
    
    def _define_success_metrics(
        self,
        main_topic: str,
        authority_score: float
    ) -> Dict[str, str]:
        """Define success metrics."""
        return {
            "topical_authority": f">{authority_score + 15}/100 (current: {authority_score})",
            "organic_traffic": f"+30-50% for '{main_topic}' keywords",
            "rankings": f"Top 10 for 5+ '{main_topic}' variations",
            "internal_links": "100% of mesh pages interconnected",
            "mesh_density": ">0.45 (semantic cocoon strength)"
        }
    
    def _get_authority_grade(self, score: float) -> str:
        """Convert authority score to letter grade."""
        if score >= 85:
            return "A (Excellent)"
        elif score >= 70:
            return "B (Good)"
        elif score >= 55:
            return "C (Fair)"
        elif score >= 40:
            return "D (Poor)"
        else:
            return "F (Very Poor)"
    
    def _get_health_grade(self, score: int) -> str:
        """Convert health score to grade."""
        if score >= 80:
            return "A (Healthy)"
        elif score >= 60:
            return "B (Good)"
        elif score >= 40:
            return "C (Needs Work)"
        else:
            return "F (Critical)"
    
    def _generate_audit_summary(self, health_score: int, issues: List[Dict]) -> str:
        """Generate human-readable audit summary."""
        grade = self._get_health_grade(health_score)
        
        summary = f"Mesh Health: {health_score}/100 - {grade}\n\n"
        
        if health_score >= 80:
            summary += "✅ Your topical mesh is strong and well-structured."
        elif health_score >= 60:
            summary += "⚠️ Your mesh is functional but has room for improvement."
        else:
            summary += "🚨 Your mesh needs significant strengthening."
        
        if issues:
            summary += f"\n\nFound {len(issues)} issues requiring attention."
        
        return summary


# Convenience functions for standalone usage

def analyze_topic_mesh(
    main_topic: str,
    subtopics: List[str],
    business_goals: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Quick function to analyze a topical mesh.
    
    Args:
        main_topic: Central topic
        subtopics: Related subtopics
        business_goals: Business objectives
        
    Returns:
        Complete mesh analysis
    """
    architect = TopicalMeshArchitect()
    return architect.analyze_topical_mesh(
        main_topic=main_topic,
        subtopics=subtopics,
        business_goals=business_goals
    )


def design_new_mesh(
    main_topic: str,
    business_goals: List[str],
    target_pages: int = 10
) -> Dict[str, Any]:
    """
    Quick function to design a new topical mesh from scratch.
    
    Args:
        main_topic: Central topic
        business_goals: Business objectives
        target_pages: Number of pages to plan
        
    Returns:
        Complete mesh design
    """
    architect = TopicalMeshArchitect()
    return architect.design_mesh_from_scratch(
        main_topic=main_topic,
        business_goals=business_goals,
        target_pages=target_pages
    )
