import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectGroup,
  SelectLabel,
  SelectItem,
  SelectSeparator,
} from 'varuflow-ui';

export function BasicSelect() {
  return (
    <div style={{ width: 280 }}>
      <Select defaultValue="net30">
        <SelectTrigger>
          <SelectValue placeholder="Select payment terms…" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="net14">Net 14 days</SelectItem>
          <SelectItem value="net30">Net 30 days</SelectItem>
          <SelectItem value="net60">Net 60 days</SelectItem>
          <SelectItem value="prepaid">Prepaid</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

export function GroupedSelect() {
  return (
    <div style={{ width: 280 }}>
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Assign to staff member…" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Sales</SelectLabel>
            <SelectItem value="anna">Anna Lindberg</SelectItem>
            <SelectItem value="bjorn">Björn Eriksson</SelectItem>
          </SelectGroup>
          <SelectSeparator />
          <SelectGroup>
            <SelectLabel>Support</SelectLabel>
            <SelectItem value="maja">Maja Olsen</SelectItem>
            <SelectItem value="lars">Lars Haugen</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}

export function DisabledTrigger() {
  return (
    <div style={{ width: 280 }}>
      <Select disabled>
        <SelectTrigger>
          <SelectValue placeholder="Not available" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
