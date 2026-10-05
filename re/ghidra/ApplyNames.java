// Ghidra headless script: apply symbol names from names.txt.
// Line format:  <addr> <name> [# comment]
//   addr = "SSSS:OOOO" (Ghidra segment:offset; Turbo Pascal puts every unit in its own code
//   segment) or "ds:XXXX" (data in DGROUP). A line "dseg SSSS" sets the DGROUP segment.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.nio.file.*;

public class ApplyNames extends GhidraScript {
    @Override
    public void run() throws Exception {
        String file = getScriptArgs().length > 0 ? getScriptArgs()[0] : "names.txt";
        int n = 0;
        String dseg = null;
        for (String line : Files.readAllLines(Paths.get(file))) {
            String comment = null;
            int h = line.indexOf('#');
            if (h >= 0) { comment = line.substring(h + 1).trim(); line = line.substring(0, h); }
            String[] p = line.trim().split("\\s+");
            if (p.length < 2) continue;
            if (p[0].equals("dseg")) { dseg = p[1]; continue; }
            boolean data = p[0].startsWith("ds:");
            if (data && dseg == null) throw new IllegalStateException("ds: address before dseg line");
            Address a = toAddr(data ? dseg + ":" + p[0].substring(3) : p[0]);
            if (!data) {
                Function f = getFunctionAt(a);
                if (f == null) { disassemble(a); new CreateFunctionCmd(a).applyTo(currentProgram); f = getFunctionAt(a); }
                if (f != null) { f.setName(p[1], SourceType.USER_DEFINED); if (comment != null) f.setComment(comment); }
            } else {
                createLabel(a, p[1], true, SourceType.USER_DEFINED);
                if (comment != null) setEOLComment(a, comment);
            }
            n++;
        }
        println("applied " + n + " names");
    }
}
