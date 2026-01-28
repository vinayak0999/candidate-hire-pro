import { useState, useEffect } from 'react';
import InPageBrowser from '../components/InPageBrowser';
import './InPageBrowserDemo.css';

// Simulated content (would come from API)
const DOCUMENT_CONTENT: Record<string, string> = {
    'doc-1': `
        <h2>Problem Statement</h2>
        <p>You are given an array of <strong>N</strong> integers. Your task is to find the maximum sum of a contiguous subarray.</p>
        <p>This is also known as <em>Kadane's Algorithm</em> problem.</p>
        <blockquote>Note: At least one element must be included in the answer.</blockquote>
    `,
    'doc-2': `
        <h2>Input Format</h2>
        <ul>
            <li>First line contains an integer <code>N</code> (1 ≤ N ≤ 10⁵)</li>
            <li>Second line contains N space-separated integers</li>
        </ul>
        <pre><code>5
-2 1 -3 4 -1 2 1 -5 4</code></pre>
    `,
    'doc-3': `
        <h2>Output Format</h2>
        <p>Print a single integer — the maximum sum of a contiguous subarray.</p>
        <pre><code>6</code></pre>
        <p>Explanation: The subarray [4, -1, 2, 1] has the maximum sum of 6.</p>
    `,
    'doc-4': `
        <h2>Constraints</h2>
        <table>
            <tr><th>Variable</th><th>Range</th></tr>
            <tr><td>N</td><td>1 ≤ N ≤ 10⁵</td></tr>
            <tr><td>Array elements</td><td>-10⁹ ≤ a[i] ≤ 10⁹</td></tr>
            <tr><td>Time Limit</td><td>1 second</td></tr>
            <tr><td>Memory</td><td>256 MB</td></tr>
        </table>
    `,
    'doc-5': `
        <h2>Examples</h2>
        <h3>Example 1</h3>
        <pre><code>Input:
5
1 2 3 4 5

Output:
15</code></pre>
        
        <h3>Example 2</h3>
        <pre><code>Input:
3
-1 -2 -3

Output:
-1</code></pre>
    `,
};

// Simulated document data
const SAMPLE_DOCUMENTS = [
    { id: 'doc-1', title: 'Problem Statement', content: DOCUMENT_CONTENT['doc-1'] },
    { id: 'doc-2', title: 'Input Format', content: DOCUMENT_CONTENT['doc-2'] },
    { id: 'doc-3', title: 'Output Format', content: DOCUMENT_CONTENT['doc-3'] },
    { id: 'doc-4', title: 'Constraints', content: DOCUMENT_CONTENT['doc-4'] },
    { id: 'doc-5', title: 'Examples', content: DOCUMENT_CONTENT['doc-5'] },
];

// Sample HTML content for the iframe
const TASK_HTML = `
    <h1>📝 Maximum Subarray Sum</h1>
    <p>Welcome to the coding challenge! Read the problem carefully and implement your solution.</p>
    
    <h2>Quick Overview</h2>
    <p>Given an array of integers, find the <strong>maximum sum</strong> of any contiguous subarray.</p>
    
    <h3>Approach Hints</h3>
    <ol>
        <li>Consider using dynamic programming</li>
        <li>Track the current maximum and global maximum</li>
        <li>Handle edge cases with all negative numbers</li>
    </ol>
    
    <h3>Starter Code</h3>
    <pre><code>function maxSubArray(nums: number[]): number {
    // Your implementation here
    let maxSum = nums[0];
    let currentSum = nums[0];
    
    for (let i = 1; i < nums.length; i++) {
        currentSum = Math.max(nums[i], currentSum + nums[i]);
        maxSum = Math.max(maxSum, currentSum);
    }
    
    return maxSum;
}</code></pre>

    <h3>Test Your Solution</h3>
    <table>
        <tr>
            <th>Input</th>
            <th>Expected Output</th>
        </tr>
        <tr>
            <td>[-2, 1, -3, 4, -1, 2, 1, -5, 4]</td>
            <td>6</td>
        </tr>
        <tr>
            <td>[1]</td>
            <td>1</td>
        </tr>
        <tr>
            <td>[5, 4, -1, 7, 8]</td>
            <td>23</td>
        </tr>
    </table>
`;

export default function InPageBrowserDemo() {
    const [timer, setTimer] = useState(3600); // 1 hour timer

    // Timer countdown - demonstrates that iframe doesn't re-render
    useEffect(() => {
        const interval = setInterval(() => {
            setTimer(prev => (prev > 0 ? prev - 1 : 0));
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="demo-container">
            <div className="demo-header">
                <h1>In-Page Browser Demo</h1>
                <div className="demo-timer">
                    ⏱️ {Math.floor(timer / 60)}:{(timer % 60).toString().padStart(2, '0')}
                </div>
            </div>

            <div className="demo-content">
                <InPageBrowser
                    htmlContent={TASK_HTML}
                    documents={SAMPLE_DOCUMENTS}
                />
            </div>

            <div className="demo-info">
                <p>
                    <strong>Performance Note:</strong> The iframe is wrapped in <code>React.memo</code> and
                    will NOT re-render when the timer updates or sidebar interactions occur.
                </p>
            </div>
        </div>
    );
}
