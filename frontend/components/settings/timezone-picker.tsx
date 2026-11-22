"use client";

import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/** IANA zones known to this browser ("UTC" first). Browser-only: mount client-side. */
export function browserZones(): string[] {
  const all = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
  return ["UTC", ...all.filter((z) => z !== "UTC")];
}

export function browserZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

/** A searchable timezone combobox. */
export function TimezonePicker({
  value,
  onChange,
  disabled,
  id,
}: {
  value: string;
  onChange: (zone: string) => void;
  disabled?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [zones] = useState(browserZones);
  const list = zones.includes(value) ? zones : [value, ...zones];
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id={id} variant="outline" role="combobox" aria-expanded={open} disabled={disabled} className="w-full justify-between font-normal sm:w-72">
          <span className="truncate">{value}</span>
          <ChevronsUpDownIcon className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search timezones…" />
          <CommandList>
            <CommandEmpty>No timezone found.</CommandEmpty>
            <CommandGroup>
              {list.map((z) => (
                <CommandItem
                  key={z}
                  value={z}
                  onSelect={() => {
                    onChange(z);
                    setOpen(false);
                  }}
                >
                  <CheckIcon className={cn(z === value ? "opacity-100" : "opacity-0")} />
                  {z}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
