package com.tcc.orderprocessor.exp;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.lang.management.ClassLoadingMXBean;
import java.lang.management.CompilationMXBean;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.RuntimeMXBean;
import java.lang.management.ThreadMXBean;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Exploratory instrumentation (exp-lazy). Records named points with timing, class loading, JIT, GC, CPU and
 * /proc/stat counters. Points are buffered and printed ("EXP_LAZY {json}") only at the end of init and at the
 * end of each invocation, outside the measured intervals.
 */
public final class LazyProbe {

	private static final ClassLoadingMXBean CLASSES = ManagementFactory.getClassLoadingMXBean();
	private static final CompilationMXBean JIT = ManagementFactory.getCompilationMXBean();
	private static final ThreadMXBean THREADS = ManagementFactory.getThreadMXBean();
	private static final com.sun.management.OperatingSystemMXBean OS =
			(com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
	private static final List<GarbageCollectorMXBean> GCS = ManagementFactory.getGarbageCollectorMXBeans();
	private static final List<String> BUFFER = new ArrayList<>();
	private static final byte[] STAT_BUF = new byte[512];

	private static int invocation = 0;
	private static String requestId = "init";

	private LazyProbe() {
	}

	public static void mark(String point) {
		mark(point, null);
	}

	public static synchronized void mark(String point, String extra) {
		long tn = System.nanoTime();
		long wall = System.currentTimeMillis();
		long gcMs = 0;
		long gcN = 0;
		for (GarbageCollectorMXBean gc : GCS) {
			gcMs += Math.max(0, gc.getCollectionTime());
			gcN += Math.max(0, gc.getCollectionCount());
		}
		long[] stat = procStat();
		StringBuilder sb = new StringBuilder(320);
		sb.append("{\"pt\":\"").append(point).append('"')
				.append(",\"inv\":").append(invocation)
				.append(",\"rid\":\"").append(requestId).append('"')
				.append(",\"tn\":").append(tn)
				.append(",\"wall\":").append(wall)
				.append(",\"cls\":").append(CLASSES.getLoadedClassCount())
				.append(",\"clsTot\":").append(CLASSES.getTotalLoadedClassCount())
				.append(",\"jitMs\":").append(JIT.getTotalCompilationTime())
				.append(",\"gcMs\":").append(gcMs)
				.append(",\"gcN\":").append(gcN)
				.append(",\"pcpuNs\":").append(OS.getProcessCpuTime())
				.append(",\"tcpuNs\":").append(THREADS.getCurrentThreadCpuTime())
				.append(",\"thr\":\"").append(esc(Thread.currentThread().getName())).append('"')
				.append(",\"statUser\":").append(stat[0])
				.append(",\"statSys\":").append(stat[1])
				.append(",\"statIdle\":").append(stat[2])
				.append(",\"statSteal\":").append(stat[3])
				.append(",\"statTotal\":").append(stat[4]);
		if (extra != null) {
			sb.append(",\"x\":\"").append(esc(extra)).append('"');
		}
		sb.append('}');
		BUFFER.add(sb.toString());
	}

	/** Header with JVM facts, printed once in init. */
	public static synchronized void meta() {
		RuntimeMXBean rt = ManagementFactory.getRuntimeMXBean();
		StringBuilder sb = new StringBuilder(512);
		sb.append("{\"pt\":\"meta\"")
				.append(",\"jvmStartMs\":").append(rt.getStartTime())
				.append(",\"uptimeMs\":").append(rt.getUptime())
				.append(",\"wall\":").append(System.currentTimeMillis())
				.append(",\"tn\":").append(System.nanoTime())
				.append(",\"cpus\":").append(Runtime.getRuntime().availableProcessors())
				.append(",\"maxHeap\":").append(Runtime.getRuntime().maxMemory())
				.append(",\"javaVersion\":\"").append(esc(System.getProperty("java.version"))).append('"')
				.append(",\"vm\":\"").append(esc(System.getProperty("java.vm.version"))).append('"')
				.append(",\"memEnv\":\"").append(esc(System.getenv("AWS_LAMBDA_FUNCTION_MEMORY_SIZE"))).append('"')
				.append(",\"execEnv\":\"").append(esc(System.getenv("AWS_EXECUTION_ENV"))).append('"')
				.append(",\"prep\":\"").append(esc(System.getenv("EXP_LAZY_PREP"))).append('"')
				.append(",\"jto\":\"").append(esc(System.getenv("JAVA_TOOL_OPTIONS"))).append('"')
				.append(",\"args\":\"").append(esc(String.join(" ", rt.getInputArguments()))).append('"')
				.append('}');
		BUFFER.add(sb.toString());
	}

	public static synchronized void beginInvocation(String rid) {
		invocation++;
		requestId = rid;
	}

	public static synchronized int invocation() {
		return invocation;
	}

	/** Lists java.io.tmpdir (e.g. native libraries extracted on first use). */
	public static synchronized void tmpListing() {
		File[] files = new File(System.getProperty("java.io.tmpdir", "/tmp")).listFiles();
		String names = files == null ? "" : String.join(";", Arrays.stream(files).map(File::getName).sorted().toList());
		BUFFER.add("{\"pt\":\"tmp\",\"inv\":" + invocation + ",\"rid\":\"" + requestId + "\",\"x\":\"" + esc(names) + "\"}");
	}

	public static synchronized void flush() {
		for (String line : BUFFER) {
			System.out.println("EXP_LAZY " + line);
		}
		System.out.flush();
		BUFFER.clear();
	}

	/** First "cpu" line of /proc/stat: user(+nice), system(+irq+softirq), idle(+iowait), steal, total (jiffies). */
	private static long[] procStat() {
		long[] out = {-1, -1, -1, -1, -1};
		try (FileInputStream in = new FileInputStream("/proc/stat")) {
			int n = in.read(STAT_BUF);
			if (n <= 0) {
				return out;
			}
			int end = 0;
			while (end < n && STAT_BUF[end] != '\n') {
				end++;
			}
			String[] f = new String(STAT_BUF, 0, end, StandardCharsets.US_ASCII).trim().split("\\s+");
			long[] v = new long[f.length];
			long total = 0;
			for (int i = 1; i < f.length; i++) {
				v[i] = Long.parseLong(f[i]);
				if (i <= 8) {
					total += v[i];
				}
			}
			out[0] = v[1] + v[2];
			out[1] = v[3] + v[6] + v[7];
			out[2] = v[4] + v[5];
			out[3] = f.length > 8 ? v[8] : 0;
			out[4] = total;
		}
		catch (IOException | RuntimeException ignored) {
			// counters stay -1
		}
		return out;
	}

	private static String esc(String s) {
		if (s == null) {
			return "";
		}
		return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ");
	}

}
