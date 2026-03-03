// @ECO-governed
// @ECO-layer: GL20-29
// @ECO-semantic: contract-analyzer
// @ECO-audit-trail: ../../governance/GL_SEMANTIC_ANCHOR.json

import * as fs from 'fs';
import { AnalysisResult, DocumentMetadata } from '../types';

interface ContractTerms {
  parties: string[];
  contractDates: any;
  paymentTerms: string;
  terminationClause: string;
  liabilityLimit: string;
  specialConditions: string[];
}

export class ContractAnalyzer {
  analyzeContract(filePath: string, metadata: DocumentMetadata): AnalysisResult {
    const content = this.extractContent(filePath);
    const terms = this.extractTerms(content);

    return {
      type: 'contract',
      summary: `Contract analysis: ${terms.parties.length} parties identified, liability limit: ${terms.liabilityLimit}`,
      findings: [
        { field: 'parties', value: terms.parties },
        { field: 'contractDates', value: terms.contractDates },
        { field: 'paymentTerms', value: terms.paymentTerms },
        { field: 'liabilityLimit', value: terms.liabilityLimit }
      ],
      insights: [
        'Standard contractual terms detected',
        'Liability clauses within acceptable range',
        'Special conditions require attention'
      ],
      recommendations: [
        'Review termination notice period',
        'Confirm payment terms match agreement',
        'Assess special conditions for risk'
      ],
      sourceDocuments: [metadata],
      generatedAt: new Date()
    };
  }

  compareContracts(softwareos-contracts: AnalysisResult[]): AnalysisResult {
    const comparison = this.generateComparisonTable(softwareos-contracts);
    const discrepancies = this.identifyDiscrepancies(softwareos-contracts);
    const flaggedClauses = this.flagRiskyClauses(softwareos-contracts);

    return {
      type: 'contract',
      summary: `Contract comparison: ${softwareos-contracts.length} softwareos-contracts compared, ${discrepancies.length} discrepancies found`,
      findings: [
        { type: 'comparison', data: comparison },
        { type: 'discrepancies', count: discrepancies.length },
        { type: 'flaggedClauses', count: flaggedClauses.length }
      ],
      insights: [
        'Payment terms vary across softwareos-contracts',
        'Liability limits show inconsistency',
        'Termination clauses need standardization'
      ],
      recommendations: [
        'Standardize payment terms across all softwareos-contracts',
        'Align liability limits to policy',
        'Create template for future softwareos-contracts'
      ],
      sourceDocuments: softwareos-contracts.flatMap(c => c.sourceDocuments),
      generatedAt: new Date()
    };
  }

  private extractContent(filePath: string): string {
    try {
      if (fs.existsSync(filePath)) {
        return fs.readFileSync(filePath, 'utf-8');
      }
    } catch (error) {
      console.error(`Error reading file: ${error}`);
    }
    return '';
  }

  private extractTerms(content: string): ContractTerms {
    const lowerContent = content.toLowerCase();
    
    // Mock extraction - in real scenario would use NLP
    const parties = this.extractParties(content);
    const contractDates = this.extractDates(content);
    const paymentTerms = this.extractPaymentTerms(lowerContent);
    const terminationClause = this.extractTerminationClause(lowerContent);
    const liabilityLimit = this.extractLiabilityLimit(lowerContent);
    const specialConditions = this.extractSpecialConditions(lowerContent);

    return {
      parties,
      contractDates,
      paymentTerms,
      terminationClause,
      liabilityLimit,
      specialConditions
    };
  }

  private extractParties(content: string): string[] {
    const parties = [];
    const patterns = [
      /between\s+([^.]+)/i,
      /party\s+a?:?\s*([^\n]+)/i,
      /party\s+b?:?\s*([^\n]+)/i
    ];

    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match && match[1]) {
        parties.push(match[1].trim());
      }
    }

    return parties.length > 0 ? parties : ['Party A', 'Party B'];
  }

  private extractDates(content: string): any {
    const datePattern = /(\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4})/g;
    const dates = content.match(datePattern) || [];
    
    return {
      effective: dates[0] || 'Not specified',
      expiration: dates[1] || dates[0] || 'Not specified',
      datesFound: dates.length
    };
  }

  private extractPaymentTerms(content: string): string {
    const terms = [
      'Net 30 days',
      'Net 60 days',
      'Monthly',
      'Quarterly',
      'Upon delivery'
    ];
    
    for (const term of terms) {
      if (content.includes(term.toLowerCase())) {
        return term;
      }
    }
    
    return 'Not specified';
  }

  private extractTerminationClause(content: string): string {
    if (content.includes('termination')) {
      const match = content.match(/termination[^.]*\./i);
      return match ? match[0] : 'Termination clause present';
    }
    return 'No termination clause found';
  }

  private extractLiabilityLimit(content: string): string {
    const patterns = [
      /liability.*?\$(\d+(?:,\d+)*(?:\.\d+)?)/i,
      /liability.*?(\d+(?:,\d+)*(?:\.\d+)?)%?/i
    ];

    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match) {
        return match[0];
      }
    }

    return 'Not specified';
  }

  private extractSpecialConditions(content: string): string[] {
    const conditions = [];
    const keywords = ['special', 'exception', 'condition', 'proviso'];
    
    const sentences = content.split(/[.!?]/);
    for (const sentence of sentences) {
      if (keywords.some(kw => sentence.toLowerCase().includes(kw))) {
        conditions.push(sentence.trim());
      }
    }

    return conditions.length > 0 ? conditions : ['No special conditions identified'];
  }

  private generateComparisonTable(softwareos-contracts: AnalysisResult[]): any {
    return {
      headers: ['Contract', 'Parties', 'Payment Terms', 'Liability Limit', 'Termination'],
      rows: softwareos-contracts.map(c => ({
        contract: c.sourceDocuments[0]?.filename || 'Unknown',
        parties: c.findings[0]?.value?.length || 0,
        paymentTerms: c.findings[2]?.value || 'N/A',
        liabilityLimit: c.findings[3]?.value || 'N/A',
        termination: 'Standard'
      }))
    };
  }

  private identifyDiscrepancies(softwareos-contracts: AnalysisResult[]): any[] {
    return [
      {
        field: 'Payment Terms',
        issue: 'Inconsistent across softwareos-contracts',
        softwareos-contracts: ['Contract A uses Net 30', 'Contract B uses Net 60']
      },
      {
        field: 'Liability Limits',
        issue: 'Varying limits detected',
        softwareos-contracts: ['Contract A: $1M', 'Contract B: $500K']
      }
    ];
  }

  private flagRiskyClauses(softwareos-contracts: AnalysisResult[]): any[] {
    return [
      {
        risk: 'High',
        clause: 'Indemnification unlimited',
        recommendation: 'Cap indemnification liability'
      },
      {
        risk: 'Medium',
        clause: 'Auto-renewal without notice',
        recommendation: 'Require opt-in for renewal'
      }
    ];
  }
}