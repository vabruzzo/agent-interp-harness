<script lang="ts">
	import type { Step, ToolCall, ObservationResult, SubagentTrajectoryRef } from "$lib/types/atif";
	import StepGroup from "./StepGroup.svelte";
	import UserMessage from "./UserMessage.svelte";
	import SystemMessage from "./SystemMessage.svelte";

	export type StepItem =
		| { kind: "thinking"; content: string }
		| { kind: "text"; content: string }
		| { kind: "tool"; call: ToolCall; result?: ObservationResult };

	interface StepGroupData {
		source: "agent" | "user" | "system";
		steps: Step[];
		items: StepItem[];
		agentGroupIndex?: number; // Nth agent group (0-based)
	}

	let {
		steps,
		runName = "",
		sessionIndex = 0 as number | string,
		mainRequestIndices = [] as number[],
		hasRawDumps = false,
		resamples = {} as Record<number, number>,
	}: {
		steps: Step[];
		runName?: string;
		sessionIndex?: number | string;
		mainRequestIndices?: number[];
		hasRawDumps?: boolean;
		resamples?: Record<number, number>;
	} = $props();

	function getMessageText(msg: string | { type: string; text?: string }[]): string {
		if (typeof msg === "string") return msg;
		if (!Array.isArray(msg)) return "";
		return msg
			.filter((p) => p.type === "text" && p.text)
			.map((p) => p.text!)
			.join("\n");
	}

	// Build a map of tool_call_id → ObservationResult from all steps
	function buildResultMap(allSteps: Step[]): Map<string, ObservationResult> {
		const map = new Map<string, ObservationResult>();
		for (const step of allSteps) {
			if (step.observation?.results) {
				for (const r of step.observation.results) {
					if (r.source_call_id) map.set(r.source_call_id, r);
				}
			}
		}
		return map;
	}

	let groups = $derived.by(() => {
		const result: StepGroupData[] = [];
		const resultMap = buildResultMap(steps);
		let agentGroupCounter = 0;

		function newAgentGroup(): StepGroupData {
			const g: StepGroupData = {
				source: "agent",
				steps: [],
				items: [],
				agentGroupIndex: agentGroupCounter++,
			};
			result.push(g);
			return g;
		}

		let current: StepGroupData | null = null;

		for (const step of steps) {
			if (step.source !== "agent") {
				current = null;
				result.push({
					source: step.source as "user" | "system",
					steps: [step],
					items: [{ kind: "text", content: getMessageText(step.message) }],
				});
				continue;
			}

			const hasThinking = !!step.reasoning_content;
			const hasToolCalls = !!(step.tool_calls && step.tool_calls.length > 0);
			const hasText = !!getMessageText(step.message).trim();
			const groupHasToolCalls = current?.items.some((i) => i.kind === "tool");

			// Start a new turn when thinking or text appears after tool calls
			// (indicates a new API response)
			if (!current || ((hasThinking || hasText) && groupHasToolCalls)) {
				current = newAgentGroup();
			}

			current.steps.push(step);

			// Add items in the order they appear in the step
			if (hasThinking) {
				current.items.push({ kind: "thinking", content: step.reasoning_content! });
			}
			if (hasText) {
				current.items.push({ kind: "text", content: getMessageText(step.message) });
			}
			if (hasToolCalls) {
				for (const tc of step.tool_calls!) {
					const obsResult = resultMap.get(tc.tool_call_id);
					current.items.push({ kind: "tool", call: tc, result: obsResult });
				}
			}
		}
		return result;
	});
</script>

<div class="space-y-6 py-2">
	{#each groups as group, i}
		{#if group.source === "user"}
			<UserMessage
				text={group.items.map((it) => it.kind === "text" ? it.content : "").join("\n")}
				isFirst={i === 0}
				stepId={group.steps[0]?.step_id}
			/>
		{:else if group.source === "system"}
			<SystemMessage
				text={group.items.map((it) => it.kind === "text" ? it.content : "").join("\n")}
				stepId={group.steps[0]?.step_id}
			/>
		{:else}
			{@const agentIdx = group.agentGroupIndex ?? 0}
			{@const requestIndex = mainRequestIndices[agentIdx] ?? undefined}
			{@const sampleCount = requestIndex !== undefined ? (resamples[requestIndex] ?? 0) : 0}
			<StepGroup
				items={group.items}
				stepIds={group.steps.map((s) => s.step_id)}
				{runName}
				{sessionIndex}
				{requestIndex}
				canResample={hasRawDumps && requestIndex !== undefined}
				existingResampleCount={sampleCount}
			/>
		{/if}
	{/each}
</div>
